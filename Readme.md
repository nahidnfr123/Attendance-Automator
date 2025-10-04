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
User=nahid
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





##### CLAUDE


sudo nano ~/.config/systemd/user/attendance-checkin.service

```
[Unit]
Description=Attendance Check-in on Startup
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStartPre=/bin/sleep 30
ExecStart=/usr/bin/python3 /path/to/attendance.py checkin
Environment="ATTENDANCE_EMAIL=your-email@example.com"
Environment="ATTENDANCE_PASSWORD=your-password"

[Install]
WantedBy=default.target



sudo nano ~/.config/systemd/user/attendance-checkout.service

```
[Unit]
Description=Attendance Check-out on Shutdown
DefaultDependencies=no
Before=shutdown.target

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 /path/to/attendance.py checkout
Environment="ATTENDANCE_EMAIL=your-email@example.com"
Environment="ATTENDANCE_PASSWORD=your-password"
RemainAfterExit=yes

[Install]
WantedBy=default.target





systemctl --user daemon-reload
systemctl --user enable attendance-checkin.service
systemctl --user enable attendance-checkout.service
systemctl --user start attendance-checkin.service
systemctl --user start attendance-checkout.service



# alternative 
Using Cron (Alternative)
# Check-in between 9:00-10:30 AM (runs every minute during this window)
* 9-10 * * 1-5 /usr/bin/python3 /path/to/attendance.py checkin

# Check-out between 5:00-7:00 PM (runs every minute during this window)
* 17-18 * * 1-5 /usr/bin/python3 /path/to/attendance.py checkout