# Auto-detect check-in/checkout based on time
python attendance_automator.py

# Manual actions
python attendance_automator.py checkin
python attendance_automator.py checkout

# Break tracking
python attendance_automator.py lock
python attendance_automator.py unlock

# Use the OS-specific setup from my previous instructions to trigger:
python attendance_automator.py # on startup (check-in/checkout)
python attendance_automator.py lock # on screen lock
python attendance_automator.py unlock # on screen unlock


### ------------------------------------------------------
# Set up systemd user services and timers
### ------------------------------------------------------
# Reload systemd
systemctl --user daemon-reload

# Enable all services
systemctl --user enable attendance-checkin.service
systemctl --user enable attendance-checkout.service
systemctl --user enable break-monitor.service

# Start them now
systemctl --user start attendance-checkin.service
systemctl --user start break-monitor.service


# Check status
# Check if services are running
systemctl --user status attendance-checkin.service
systemctl --user status break-monitor.service

# View logs
journalctl --user -u attendance-checkin.service -f
journalctl --user -u break-monitor.service -f