# Installing Web Service to Cast Location Data

## Pre-requisites

- **Raspberry Pi 3 or above**
- **Install Node/NPM v18 or later**
  ```sh
  sudo apt-get update
  curl -sL https://deb.nodesource.com/setup_20.x | sudo -E bash -
  sudo apt-get install -y nodejs
  node -v
  npm -v
  ```
- **Install GIT (optional, if you want to copy build artifact onto RPi yourself)**
  ```sh
  sudo apt update
  sudo apt install git -y
  git --version
  ```

## Clone Repository

Clone this repo to your Raspberry Pi:
```sh
git clone git@github.com:anking/gps-station.git
```

## Compile Driver on a Separate Machine

Clone & compile the driver repository and place the publish artifacts into `gps-station/f9p` directory (ensure correct architecture 32/64-bit).

Instructions are available in the README of the driver repository:
[zedf9p-server](https://github.com/anking/zedf9p-server)

## Install Dependencies
```sh
npm i
```

## Build the Application
```sh
npm run build
```
This will build the app and put artifacts into `./build`

## Run the Web Service Manually
```sh
npm start
```

The web service will require `f9p` driver execution permissions to spawn the driver process. Permissions should be assigned automatically, but if needed, set them manually:
```sh
chmod 744 ./build/f9p/Zedf9p
```

After starting, the network HTTP service will be available at:
```
[YOUR_IP / 192.168.0.11]:3000
```

---

## Running as a System Service

### Create a Symbolic Link for the Service
```sh
sudo ln -s /home/pi/gps-station/gpsstationweb.service /etc/systemd/system/gpsstationweb.service
```

### Reload System Daemons
```sh
sudo systemctl daemon-reload
```

### Enable the Service
```sh
sudo systemctl enable gpsstationweb
```

### Manual Control
```sh
sudo systemctl start gpsstationweb
sudo systemctl stop gpsstationweb
```

### Check Logs
```sh
journalctl -u gpsstationweb
```

### Check Status
```sh
sudo systemctl status gpsstationweb
```

---

## Auto-start Browser with Web Server Visible

Edit the autostart file:
```sh
sudo nano /etc/xdg/lxsession/LXDE-pi/autostart
```

Add the following line:
```sh
@chromium-browser --kiosk --disable-infobars --disable-session-crashed-bubble --noerrdialogs http://localhost:3000
```

---

## Using Raspberry Pi 3.5" Screen
Refer to the [Touchscreen README](./touchscreen/README.md)

---

## F9P Device Driver
Alternatively, you can use `str2str` to transfer the F9P driver data directly to the location service.
For this, use `location.service`. More info is available in `readme_old.txt`.
