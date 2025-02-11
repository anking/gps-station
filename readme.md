// INSTALLING WEB SERVICE TO CAST LOCATION DATA

// Pre-requisietes
Raspberry Pi3 or above

install node v.18 or later
curl -sL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs
node -v

// Clone repo on your Raspberry Pi

- Install dependencies
npm i

- First you can try to run the web service manually by running
node index.js

Web service will require f9p driver exec permissions to spawn driver process 
(CHMOD 744) for /f9p/Zedf9p

Also will need permissions to remove socket file in /tmp, if unable you'll need to run it like so
sudo node webserver.js

After start network http service will be running on 192.168.0.11:3000

Create a sym link to the service:
sudo ln -s /home/pi/gps-station/gpsstationweb.service /etc/systemd/system/gpsstationweb.service

Enable the service
sudo systemctl enable gpsstationweb

Manual control
sudo systemctl start gpsstationweb
sudo systemctl stop gpsstationweb

Check Logs
journalctl -u gpsstationweb

Check status
sudo systemctl status gpsstationweb

// F9P Device driver
alternatively you can run the str2str to move the F9p drive data directly into the location service you need
for this use location.service

// if f9p driver is unable to connect to the interprocess sockets giving you the following issues
F9p Driver: trying to connect to interpsrocess socket /tmp/zed-f9p-rtcm-data.sock...
F9p Driver: Socket connection error: Cannot assign requested address /tmp/zed-f9p-nmea-data.sock
