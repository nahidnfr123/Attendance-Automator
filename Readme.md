sudo apt install python3.12-venv
python3 -m venv venv
source venv/bin/activate
pip install requests python-dotenv tenacity
chmod +x attendance_automator.py



# Create a service unit /etc/systemd/system/attendance.service

'''
[Unit]
Description=Attendance Automator

[Service]
Type=oneshot
User=your-linux-username
WorkingDirectory=/var/www/attendance_automation
EnvironmentFile=/var/www/attendance_automation/.env
ExecStart=/var/www/attendance_automation/venv/bin/python /var/www/attendance_automation/attendance_automator.py


# Create timer /etc/systemd/system/attendance.timer

''' 
[Unit]
Description=Run Attendance Automator at boot and every 10 minutes

[Timer]
OnBootSec=1min
OnUnitActiveSec=10min
Persistent=true

[Install]
WantedBy=timers.target



# command
sudo systemctl daemon-reload
sudo systemctl enable --now attendance.timer