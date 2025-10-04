#!/bin/bash

dbus-monitor --session "type='signal',interface='org.gnome.ScreenSaver'" |
while read line; do
    if echo "$line" | grep -q "boolean true"; then
        /var/www/attendance_automation/venv/bin/python /var/www/attendance_automation/attendance_automator.py lock
    elif echo "$line" | grep -q "boolean false"; then
        /var/www/attendance_automation/venv/bin/python /var/www/attendance_automation/attendance_automator.py unlock
    fi
done