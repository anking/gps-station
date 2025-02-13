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
npm start (this will build the app anp put artifacts into ./build)

- Alternatively you can do
npm test (if you already have the app built)

Web service will require f9p driver exec permissions to spawn driver process
The app should be able to do it automatically
(CHMOD 744) for ./build/f9p/Zedf9p

After start network http service will be running on [YOUR_IP / 192.168.0.11]:3000

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


// To autostart browser with webserver visible
sudo nano /etc/xdg/lxsession/LXDE-pi/autostart


// F9P Device driver
alternatively you can run the str2str to move the F9p drive data directly into the location service you need
for this use location.service
