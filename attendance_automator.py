#!/usr/bin/env python3
"""
attendance_automator.py

Usage:
  - Run on startup or via scheduler for check-in/check-out
  - Run with 'lock' or 'unlock' argument for break tracking

Requirements:
  pip install requests python-dotenv tenacity

Environment variables (can be in a .env file):
  API_BASE_URL   e.g. https://company.example.com
  EMAIL
  PASSWORD
  TZ             e.g. America/Chicago  (optional; defaults to system timezone)
  DRY_RUN        "1" to not actually send check-in/out (for testing)
  LOG_FILE       optional path for logs
"""

import os
import json
import sys
from datetime import datetime, time, date, timedelta
from pathlib import Path
import logging
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from dotenv import load_dotenv

try:
    # Python 3.9+: zoneinfo
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None  # we'll fallback to naive local tz if not available

# ---------------------------
# Config
# ---------------------------

# load .env if present
load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL", "").rstrip("/")
EMAIL = os.getenv("EMAIL", "")
PASSWORD = os.getenv("PASSWORD", "")
TZ_NAME = os.getenv("TZ", None)  # e.g. "America/Chicago"
DRY_RUN = os.getenv("DRY_RUN", "0") == "1"
LOG_FILE = os.getenv("LOG_FILE", "")  # optional
STATE_DIR = Path.home() / ".attendance_automator"
STATE_DIR.mkdir(parents=True, exist_ok=True)
STATE_FILE = STATE_DIR / "state.json"
BREAK_STATE_FILE = STATE_DIR / "break_state.json"

# Time windows (local times)
CHECKIN_START = time(8, 0)
CHECKIN_END = time(10, 30)

CHECKOUT_START = time(17, 0)
CHECKOUT_END = time(19, 30)

LOGIN_ENDPOINT = "/api/login"
CHECKIN_ENDPOINT = "/api/attendances/check-in"
CHECKOUT_ENDPOINT = "/api/attendances/check-out"
BREAK_START_ENDPOINT = "/api/breaks/start"
BREAK_END_ENDPOINT = "/api/breaks/end"

# logging
logger = logging.getLogger("attendance_automator")
logger.setLevel(logging.INFO)
fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
h = logging.StreamHandler(sys.stdout)
h.setFormatter(fmt)
logger.addHandler(h)
if LOG_FILE:
    fh = logging.FileHandler(LOG_FILE)
    fh.setFormatter(fmt)
    logger.addHandler(fh)


# ---------------------------
# Helpers
# ---------------------------

def get_zoneinfo():
    if TZ_NAME:
        try:
            if ZoneInfo:
                return ZoneInfo(TZ_NAME)
            else:
                logger.warning("zoneinfo not available (old Python). Using system local time.")
                return None
        except Exception as e:
            logger.warning(f"Invalid TZ '{TZ_NAME}': {e}. Using system local time.")
            return None
    else:
        if ZoneInfo:
            # try local timezone by system setting is not straightforward without tzlocal,
            # so we'll return None to use naive datetimes with system local time.
            return None
        return None


TZ = get_zoneinfo()


def now_local():
    # Return timezone-aware datetime if TZ set/available, otherwise naive local datetime
    if TZ:
        return datetime.now(TZ)
    return datetime.now()


def iso_now():
    dt = now_local()
    if dt.tzinfo:
        return dt.isoformat()
    else:
        # append local offset unknown; produce ISO-like without tz
        return dt.replace(microsecond=0).isoformat()


def is_weekend(dt=None):
    dt = dt or now_local()
    # weekday(): Mon=0, Sun=6
    return dt.weekday() >= 5


def in_time_window(dt_time, start: time, end: time):
    # dt_time: a time object (from datetime)
    return (start <= dt_time <= end)


# ---------------------------
# State management
# ---------------------------

def read_state():
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        logger.warning(f"Failed to read state file: {e}")
        return {}


def write_state(state):
    tmp = STATE_FILE.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    tmp.replace(STATE_FILE)


def state_for_today():
    st = read_state()
    today_str = date.today().isoformat()
    return st.get(today_str, {"checkin": None, "checkout": None})


def set_state_for_today(key, value):
    st = read_state()
    today_str = date.today().isoformat()
    if today_str not in st:
        st[today_str] = {"checkin": None, "checkout": None}
    st[today_str][key] = value
    # optionally prune old days (keep last 30)
    keys = sorted(st.keys())
    if len(keys) > 30:
        for k in keys[:-30]:
            st.pop(k, None)
    write_state(st)


# ---------------------------
# Break state management
# ---------------------------

def read_break_state():
    try:
        with open(BREAK_STATE_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"on_break": False, "break_start_time": None}
    except Exception as e:
        logger.warning(f"Failed to read break state file: {e}")
        return {"on_break": False, "break_start_time": None}


def write_break_state(state):
    tmp = BREAK_STATE_FILE.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    tmp.replace(BREAK_STATE_FILE)


def is_on_break():
    state = read_break_state()
    return state.get("on_break", False)


def set_break_started():
    write_break_state({"on_break": True, "break_start_time": iso_now()})


def set_break_ended():
    write_break_state({"on_break": False, "break_start_time": None})


# ---------------------------
# Networking with retry
# ---------------------------

session = requests.Session()
session.headers.update({"User-Agent": "attendance-automator/1.0"})


class NetworkError(Exception):
    pass


@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=1, max=10),
       retry=retry_if_exception_type((requests.RequestException, NetworkError)))
def post_with_retry(url, json_payload=None, headers=None, timeout=10):
    try:
        resp = session.post(url, json=json_payload, headers=headers, timeout=timeout)
    except requests.RequestException as e:
        logger.debug(f"Request exception: {e}")
        raise
    if resp.status_code >= 500:
        logger.debug(f"Server error {resp.status_code}: will retry")
        raise NetworkError(f"server {resp.status_code}")
    return resp


def get_with_retry(url, params=None, headers=None, timeout=10):
    try:
        resp = session.get(url, params=params, headers=headers, timeout=timeout)
    except requests.RequestException as e:
        logger.debug(f"Request exception: {e}")
        raise
    if resp.status_code >= 500:
        print(resp.text)
        logger.debug(f"Server error {resp.status_code}: will retry")
        raise NetworkError(f"server {resp.status_code}")
    return resp


def extract_token_from_login_json(j):
    # try a few common fields
    for key in ("token", "access_token", "accessToken", "auth_token", "bearer"):
        if isinstance(j, dict) and key in j and isinstance(j[key], str) and j[key]:
            return j[key]
    # sometimes login returns {"data": {"token": "..."}}
    if isinstance(j, dict) and "data" in j and isinstance(j["data"], dict):
        return extract_token_from_login_json(j["data"])
    # sometimes nested in attributes
    # give up
    return None


def login_and_get_token():
    if not API_BASE_URL or not EMAIL or not PASSWORD:
        raise ValueError("API_BASE_URL, EMAIL and PASSWORD must be set in environment or .env")
    url = f"{API_BASE_URL}{LOGIN_ENDPOINT}"
    payload = {"email": EMAIL, "password": PASSWORD}
    logger.info(f"Logging in to {url} as {EMAIL}")
    if DRY_RUN:
        logger.info("DRY_RUN: skipping actual login; returning fake-token")
        return "dry-run-token"
    resp = post_with_retry(url, json_payload=payload)
    try:
        j = resp.json()
    except Exception:
        logger.error(f"Login response not JSON. status={resp.status_code} text={resp.text}")
        raise NetworkError("Invalid login response")
    token = extract_token_from_login_json(j)
    if not token:
        # Try header or text fallback
        if "authorization" in resp.headers:
            token = resp.headers.get("authorization").split()[-1]
    if not token:
        logger.error(f"Could not find token in login response JSON: {j}")
        raise NetworkError("No token found")
    logger.info("Login successful; token obtained")
    return token


def do_check(endpoint, token, method="POST"):
    url = f"{API_BASE_URL}{endpoint}"
    headers = {"Authorization": f"Bearer {token}"}

    if method == "GET":
        params = {"timestamp": iso_now()}
        logger.info(f"GET {url} params={params}")
        if DRY_RUN:
            return {"status": "dry-run", "ok": True}
        resp = get_with_retry(url, params=params, headers=headers)
    else:
        payload = {"timestamp": iso_now()}
        logger.info(f"POST {url} payload={payload}")
        if DRY_RUN:
            return {"status": "dry-run", "ok": True}
        resp = post_with_retry(url, json_payload=payload, headers=headers)

    ok = 200 <= resp.status_code < 300
    try:
        j = resp.json()
    except Exception:
        j = {"text": resp.text}
    return {"status_code": resp.status_code, "ok": ok, "resp_json": j}


# ---------------------------
# Main logic: Check-in/Check-out
# ---------------------------

def attempt_checkin():
    st = state_for_today()
    if st.get("checkin"):
        logger.info("Check-in already recorded for today; skipping.")
        return
    token = login_and_get_token()
    # result = do_check(CHECKIN_ENDPOINT, token)
    result = do_check(CHECKIN_ENDPOINT, token, method="GET")
    if result.get("ok"):
        set_state_for_today("checkin", {"time": iso_now(), "resp": result.get("resp_json")})
        logger.info("✓ Check-in recorded.")
    else:
        logger.error(f"Check-in failed: {result}")


def attempt_checkout():
    st = state_for_today()
    if st.get("checkout"):
        logger.info("Check-out already recorded for today; skipping.")
        return
    token = login_and_get_token()
    # result = do_check(CHECKOUT_ENDPOINT, token)
    result = do_check(CHECKIN_ENDPOINT, token, method="GET")
    if result.get("ok"):
        set_state_for_today("checkout", {"time": iso_now(), "resp": result.get("resp_json")})
        logger.info("✓ Check-out recorded.")
    else:
        logger.error(f"Check-out failed: {result}")


def decide_and_act():
    dt = now_local()
    t = dt.time()
    logger.info(f"Now local time: {dt.isoformat() if dt else t}; weekend={is_weekend(dt)}")
    if is_weekend(dt):
        logger.info("It's weekend: no action.")
        return

    # If current time is within check-in window attempt check-in (once per day)
    if in_time_window(t, CHECKIN_START, CHECKIN_END):
        logger.info("Within check-in window.")
        attempt_checkin()
        return

    # If current time is within check-out window attempt check-out (once per day)
    if in_time_window(t, CHECKOUT_START, CHECKOUT_END):
        logger.info("Within check-out window.")
        attempt_checkout()
        return

    logger.info("Not within any action window; no action taken.")


# ---------------------------
# Break tracking: Lock/Unlock
# ---------------------------

def handle_lock():
    """Called when screen is locked (Windows+L, etc.)"""
    dt = now_local()
    logger.info(f"Screen locked at {iso_now()}; weekend={is_weekend(dt)}")

    if is_weekend(dt):
        logger.info("It's weekend: skipping break start.")
        return

    if is_on_break():
        logger.info("Already on break; skipping duplicate break start.")
        return

    try:
        token = login_and_get_token()
        result = do_check(BREAK_START_ENDPOINT, token)
        if result.get("ok"):
            set_break_started()
            logger.info("✓ Break started successfully.")
        else:
            logger.error(f"Break start failed: {result}")
    except Exception as e:
        logger.exception(f"Error starting break: {e}")


def handle_unlock():
    """Called when screen is unlocked"""
    dt = now_local()
    logger.info(f"Screen unlocked at {iso_now()}; weekend={is_weekend(dt)}")

    if is_weekend(dt):
        logger.info("It's weekend: skipping break end.")
        return

    if not is_on_break():
        logger.info("Not on break; skipping break end.")
        return

    try:
        token = login_and_get_token()
        result = do_check(BREAK_END_ENDPOINT, token)
        if result.get("ok"):
            set_break_ended()
            logger.info("✓ Break ended successfully.")
        else:
            logger.error(f"Break end failed: {result}")
    except Exception as e:
        logger.exception(f"Error ending break: {e}")


# ---------------------------
# CLI entry
# ---------------------------
if __name__ == "__main__":
    try:
        # Check for lock/unlock argument
        if len(sys.argv) > 1:
            action = sys.argv[1].lower()
            if action == "lock":
                handle_lock()
            elif action == "unlock":
                handle_unlock()
            elif action == "checkin":
                # Manual check-in
                if is_weekend():
                    logger.info("It's weekend: no action.")
                else:
                    attempt_checkin()
            elif action == "checkout":
                # Manual check-out
                if is_weekend():
                    logger.info("It's weekend: no action.")
                else:
                    attempt_checkout()
            else:
                logger.error(f"Unknown action: {action}")
                logger.info("Usage: python attendance_automator.py [lock|unlock|checkin|checkout]")
                sys.exit(1)
        else:
            # No argument: auto-detect based on time
            decide_and_act()
    except Exception as e:
        logger.exception(f"Unhandled error: {e}")
        sys.exit(2)
