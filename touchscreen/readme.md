# Raspberry Pi LCD Screen

## Overview
- LCD Screen: [3.5-inch RPi Display](https://lcdwiki.com/3.5inch_RPi_Display)
- Purchase link: [eBay](https://www.ebay.com/itm/264732551257)
- Reference manual: [TrickiKnow](https://trickiknow.com/raspberry-pi-3-complete-tutorial-2018-lets-get-started/) (scroll down for details)

## Enabling the LCD Display
### Steps:
1. Connect your Raspberry Pi to a PC monitor and attach the 3.5-inch LCD to the Pi.
2. Turn on the Pi and ensure it is connected to the Internet via WiFi or LAN.
3. Open the terminal in Raspbian desktop and run the following commands:

```sh
sudo rm -rf LCD-show 
git clone https://github.com/goodtft/LCD-show.git 
chmod -R 755 LCD-show 
cd LCD-show/
sudo ./LCD35-show
```

This will restart the Raspberry Pi. The display will now only be visible on the Raspberry Pi LCD and not on the external monitor.

## Reverting to External Monitor
To switch back to the external monitor, run:

```sh
chmod -R 755 LCD-show 
cd LCD-show/ 
sudo ./LCD-hdmi
```

## Optional Tweaks
### Disable Cursor in UI
Add the `nocursor` option in the LightDM configuration file:

```sh
sudo nano /etc/lightdm/lightdm.conf
```

Modify the following line:

```sh
xserver-command = X -nocursor
```

### Disable Screensaver
Edit the LightDM configuration:

```sh
sudo nano /etc/lightdm/lightdm.conf
```

Add or modify the following lines under `[Seat:*]`:

```sh
[Seat:*]
xserver-command=X -s 0 -dpms
```

## Known Issues
### Issue: Display Not Working on Raspberry Pi 3B+ with Debian Bookworm
A known issue prevents the display from functioning properly after installing Debian Bookworm. See this [GitHub thread](https://github.com/goodtft/LCD-show/issues/369#issuecomment-2116552991) for details.

### Fix:
The `glamor-test` service adds a conflicting display driver. Disable it using the following commands:

#### To Test:
```sh
sudo systemctl disable glamor-test.service
sudo systemctl restart lightdm
```

#### To Permanently Fix:
```sh
sudo rm /usr/share/X11/xorg.conf.d/20-noglamor.conf
sudo sed -e '/dtoverlay=vc4/ s/^#*/#/' -i /boot/firmware/config.txt
sudo sed -i -e '/greeter-session=/ s/=.*/=pi-greeter/' /etc/lightdm/lightdm.conf
sudo sed -i -e '/user-session=/ s/=.*/=LXDE-pi-x/' /etc/lightdm/lightdm.conf
sudo sed -i -e '/autologin-session=/ s/=.*/=LXDE-pi-x/' /etc/lightdm/lightdm.conf
sudo systemctl disable glamor-test.service