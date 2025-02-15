// Raspberry Pi LCD Screen (https://lcdwiki.com/3.5inch_RPi_Display)
// https://www.ebay.com/itm/264732551257
// To turn on lcd display
// As described in this manual https://trickiknow.com/raspberry-pi-3-complete-tutorial-2018-lets-get-started/ (scroll down)

Step 1: Connect your Raspberry Pi to a PC monitor, also connect the 3.5 inch LCD to Pi.
Step 2: Turn on the pi and make sure its connected to the Internet via WiFi or LAN.
Step 3: Open terminal in Raspbian desktop, and type the following commands.

sudo rm -rf LCD-show 
git clone https://github.com/goodtft/LCD-show.git 
chmod -R 755 LCD-show 
cd LCD-show/
sudo ./LCD35-show

But now the display will not visible on the monitor, it will only visible to the Raspberry Pi LCD. If you want revert back to the monitor, Open the terminal and type commands to get back.

chmod -R 755 LCD-show 
cd LCD-show/ 
sudo ./LCD-hdmi

// Disable cursor in UI / optional
I simply added a nocursor option as follows in the file (/etc/lightdm/lightdm.conf)

xserver-command = X -nocursor

// KNOWN ISSUES
On raspberry Pi 3B+ display does not work after installing Debian Bookwarm
this thread ad fix help:
https://github.com/goodtft/LCD-show/issues/369#issuecomment-2116552991
service (glamor-test) was adding a display driver for X. Since X is supposed to use the default driver, this tells it to use a different one, hence the problems you are having. Do the following on a RPi3B+:

// To test
sudo systemctl disable glamor-test.service
sudo systemctl restart lightdm

// To set
sudo rm /usr/share/X11/xorg.conf.d/20-noglamor.conf
sudo sed -e '/dtoverlay=vc4/ s/^#*/#/' -i /boot/firmware/config.txt
sudo sed -i -e '/greeter-session=/ s/=.*/=pi-greeter/' /etc/lightdm/lightdm.conf
sudo sed -i -e '/user-session=/ s/=.*/=LXDE-pi-x/' /etc/lightdm/lightdm.conf
sudo sed -i -e '/autologin-session=/ s/=.*/=LXDE-pi-x/' /etc/lightdm/lightdm.conf
sudo systemctl disable glamor-test.service

It appears that after some time the screen still shuts off after a bit. I'll try using Bullseye release instead of Bookwarm 