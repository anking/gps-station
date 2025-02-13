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