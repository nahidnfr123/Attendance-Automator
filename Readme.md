mkdir -p ~/.config/systemd/user

# Copy configuration files

cp ./config/* ~/.config/systemd/user/

[//]: # (sudo cp ./config/* /etc/systemd/system/)

# Install dependencies

sudo apt update && sudo apt install python3.12-venv
python3 -m venv venv
source venv/bin/activate
pip install requests python-dotenv tenacity

# Make Executable

chmod +x attendance_automator.py
chmod +x /var/www/attendance_automation/break-monitor.sh

# command

systemctl --user daemon-reload
systemctl --user enable attendance-checkin.service
systemctl --user enable attendance-checkout.service
systemctl --user enable break-monitor.service
systemctl --user start break-monitor.service

# Check status

# Check if services are running

systemctl --user status attendance-checkin.service
systemctl --user status break-monitor.service

# View logs

journalctl --user -u attendance-checkin.service -f
journalctl --user -u break-monitor.service -f