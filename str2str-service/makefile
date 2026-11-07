install:
	sudo ln -sf $(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))/location-streamer.service /etc/systemd/system/location-streamer.service
	#sudo systemctl enable location
	#sudo systemctl start location

# make test NTRIP_PASSWORD=... NTRIP_MOUNTPOINT=...
test:
	/usr/local/bin/str2str -in serial://ttyACM0:115200:8:n:1:off -out ntrips://:$(NTRIP_PASSWORD)@rtk2go.com:2101/$(NTRIP_MOUNTPOINT)
