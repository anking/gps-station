To start casting base station location to a public caster from a ZED-F9P board the following steps needs performed:
-raspberry pi3+ (tested)
-download and install u-center from u-blox (https://www.u-blox.com/en/product/u-center)
-connect you module via usb to the machine and observe it inside the u-center (view->configuration view)
-watch configuration videos for it:
	https://www.youtube.com/watch?v=FpkUXmM7mrc&ab_channel=RoboRoby
	https://www.youtube.com/watch?v=g92GboiOkeQ&list=PL6ZY_ezPKMtZNtV6JxSob9Vvub8b3iA47&ab_channel=SkyHorseTech
-to put device into a base mode you may and up running this file of settings as described in first video to put it in fil mode "TIME"
-download RTKLIB sources https://github.com/tomojitakasu/RTKLIB/tree/master/app
-read the manual for rtklib here: https://github.com/tomojitakasu/RTKLIB/blob/master/doc/manual_2.4.2.pdf
-install RTKLIB (only str2str) in raspberry pi environment like so:
	cd <install_dir>/rtklib/app/str2str/gcc
	make
	make install
-the above commands will compile and install str2str (if installation doesnt work read the manual above or check installation constants inside makefile)
-register an account on RTK2go, this is a public caster that will accept RTCM correction signals from the gps module and broadcast them (uses SNIP server on backend)
-run /usr/local/bin/str2str -in serial://ttyACM0:115200:8:n:1:off -out ntrips://:6n9c2TxqKwuc@rtk2go.com:2101/Wexford  //replace ttyACM0 with a mounted device name
-check service updates reports on http://rtk2go.com:2101/SNIP::STATUS#single
-install service (steps below)



some tests:

screen /dev/ttyACM0 115200 //screen needs to be installed

Ctrl-a+Ctrl-\ - Exit screen and terminate all programs in this screen. Helpful, for example, if you need to close tty connection.
Ctrl-a+d or - Ctrl-a+Ctrl-d - "minimize" screen, screen -r to restore it.



INSTALLING STR2STR SERVICE:
>sudo make install


//service configration foa automatin plugin-unplug:
https://unix.stackexchange.com/questions/446225/is-there-a-way-for-a-systemd-service-to-find-out-a-device-path-and-restart-if-it

//check udev_trigger and chmod it +x (to make executable)  // this is only used for logging

//restart systemd daemons if changed
sudo systemctl daemon-reload

//start service 
sudo systemctl start location@ttyACM0

//check running services
systemctl --type=service --state=running

//to get a list of all available device unit files use 
systemctl list-units --all --full | grep ".device"

///Check udev admin page and monitor to observe device connection and device statuses and info
udevadm monitor
udevadm info -a -n /dev/ttyACM0 | less

//add udev rule, this will allow GPS to be innitialized when plugged in and service for it will start automatically
ACTION=="add", SUBSYSTEM=="tty", KERNEL=="ttyACM*", ATTRS{idVendor}=="1546", RUN+="/home/pi/udev_trigger.sh", TAG+="systemd", ENV{SYSTEMD_WANTS}+="location@%k.service"
//to the
> sudo nano /etc/udev/rules.d/99-com.rules or other rules file that is there
//reload udev
sudo udevadm control --reload

RUNNING STR2STR AS SERVICE:

location.service file:

[Unit]
Description=RTCM Base Station

[Service]
ExecStart=/usr/local/bin/str2str -in serial://ttyACM0:115200:8:n:1:off -out ntrips://:6n9c2TxqKwuc@rtk2go.com:2101/Wexford
Restart=always
User=nobody
RestartSec=1 #restart after 1 second


Copy your service file into the /etc/systemd/system.
----do not copy/ create a softlink instead
---------Copy your service file into the /etc/systemd/system.
sudo ln -s /usr/local/ddnsupdater/ddnsupdater.service ddnsupdater.service

Start it with systemctl start myapp.

Enable it to run on boot with systemctl enable myapp. - not needed because of the device nature

See logs with journalctl -u myapp


//RTK2go
Sir or Madam: The requested mountPt has been added to the SNIP NTRIP Caster operating
at RTK2go.com:2101 and may now be used.

      The mountPt name is: Wexford  -  (this is case sensitive and must match to be used)
      With the password: 6n9c2TxqKwuc-  (also case sensitive)
      Other details [ Wexford,     USA]

If you have been connecting with another password (such as WEEK21xx) you must now use the above.
This connection is expected to use NTRIP Rev1 format (contact us if Rev2 is preferred)

//INSTALLING WEB SERVICE
network http service will be running on 192.168.0.126:3000

sudo ln -s /home/pi/gps-station/gpsstationweb.service /etc/systemd/system/gpsstationweb.service
sudo systemctl enable gpsstationweb