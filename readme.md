# Setting Up a Public Caster for a ZED-F9P Base Station

## Requirements
- Raspberry Pi 3+ (tested)
- [u-center from u-blox](https://www.u-blox.com/en/product/u-center)
- [RTKLIB sources](https://github.com/tomojitakasu/RTKLIB/tree/master/app)
- Account on [RTK2go](http://rtk2go.com)

## Setup Steps
### 1. Install and Configure u-center
- Download and install u-center from [u-blox](https://www.u-blox.com/en/product/u-center).
- Connect your ZED-F9P module via USB.
- Open u-center and navigate to **View -> Configuration View**.
- Watch the following setup guides:
  - [Video 1](https://www.youtube.com/watch?v=FpkUXmM7mrc&ab_channel=RoboRoby)
  - [Video 2](https://www.youtube.com/watch?v=g92GboiOkeQ&list=PL6ZY_ezPKMtZNtV6JxSob9Vvub8b3iA47&ab_channel=SkyHorseTech)
- Configure the device into base mode using the settings file from the first video.

### 2. Install RTKLIB
```sh
cd <install_dir>/rtklib/app/str2str/gcc
make
make install
```
- If installation fails, refer to the [RTKLIB manual](https://github.com/tomojitakasu/RTKLIB/blob/master/doc/manual_2.4.2.pdf) or check `Makefile` settings.

### 3. Register an RTK2go Account
- RTK2go is a public caster that broadcasts RTCM correction signals from the GPS module.
- Register an account on [RTK2go](http://rtk2go.com).

### 4. Run str2str to Stream Data
```sh
/usr/local/bin/str2str -in serial://ttyACM0:115200:8:n:1:off -out ntrips://:6n9c2TxqKwuc@rtk2go.com:2101/Wexford
```
- Replace `ttyACM0` with the actual mounted device name.
- Check updates at [RTK2go Status](http://rtk2go.com:2101/SNIP::STATUS#single).

### 5. Testing
```sh
screen /dev/ttyACM0 115200
```
- **Exit Screen:** `Ctrl-a` + `Ctrl-\`
- **Detach Screen:** `Ctrl-a` + `Ctrl-d`
- **Restore Screen:** `screen -r`

## Installing str2str as a Systemd Service
### 1. Install str2str
```sh
sudo make install
```

### 2. Configure Automatic Startup
- Reference: [StackExchange thread](https://unix.stackexchange.com/questions/446225/is-there-a-way-for-a-systemd-service-to-find-out-a-device-path-and-restart-if-it)
- Check and enable udev trigger:
```sh
sudo chmod +x udev_trigger.sh
```
- Reload Systemd:
```sh
sudo systemctl daemon-reload
sudo systemctl start location@ttyACM0
```
- Verify running services:
```sh
systemctl --type=service --state=running
systemctl list-units --all --full | grep ".device"
```
- Monitor udev status:
```sh
udevadm monitor
udevadm info -a -n /dev/ttyACM0 | less
```

### 3. Add Udev Rule for Automatic Initialization
Add the following line to `/etc/udev/rules.d/99-com.rules`:
```sh
ACTION=="add", SUBSYSTEM=="tty", KERNEL=="ttyACM*", ATTRS{idVendor}=="1546", RUN+="/home/pi/udev_trigger.sh", TAG+="systemd", ENV{SYSTEMD_WANTS}+="location@%k.service"
```
Reload udev:
```sh
sudo udevadm control --reload
```

### 4. Create Systemd Service for str2str
Create `location.service` in `/etc/systemd/system/`:
```ini
[Unit]
Description=RTCM Base Station

[Service]
ExecStart=/usr/local/bin/str2str -in serial://ttyACM0:115200:8:n:1:off -out ntrips://:6n9c2TxqKwuc@rtk2go.com:2101/Wexford
Restart=always
User=nobody
RestartSec=1
```
Create a symbolic link instead of copying:
```sh
sudo ln -s /usr/local/ddnsupdater/ddnsupdater.service ddnsupdater.service
```
Start and enable service:
```sh
sudo systemctl start location.service
sudo systemctl enable location.service
```
Check logs:
```sh
journalctl -u location.service
```

## RTK2go Connection Confirmation
RTK2go will confirm:
```
MountPt: Wexford
Password: 6n9c2TxqKwuc
Location: Wexford, USA
```
Ensure that the mount point name matches exactly.

## Installing Web Service
```sh
sudo ln -s /home/pi/gps-station/gpsstationweb.service /etc/systemd/system/gpsstationweb.service
sudo systemctl enable gpsstationweb
```
The network service will be available at `192.168.0.126:3000`.

---

This guide provides a step-by-step setup for casting a ZED-F9P base station's location data to a public caster using RTK2go.

