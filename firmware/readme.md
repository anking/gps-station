# GPS base station firmware for ESP32

Turns an ESP32 and a u-blox ZED-F9P into an RTK base station. It finds and configures the module, surveys or uses a fixed position, and streams RTCM corrections to an NTRIP caster such as RTK2go over WiFi. There is no Raspberry Pi, .NET or Node.js involved.

**Status:** tested against a simulated ZED-F9P and caster, and built for both boards below, but not yet run on real hardware. That includes updates and reporting, which only run on the board. See [First bench test](#first-bench-test).

## What you need

- An ESP32-S3 or classic ESP32 board with 4 MB of flash or more
- A ZED-F9P board with its UART1 pins available, and its antenna
- A [mountpoint reservation on RTK2go](http://rtk2go.com/sample-page/new-reservation/), or another caster

## Wiring

| ZED-F9P | ESP32-S3 | Classic ESP32 |
| --- | --- | --- |
| RX1 | GPIO 17 | GPIO 17 |
| TX1 | GPIO 18 | GPIO 16 |
| GND | GND | GND |

Both sides use 3.3 V logic, so no level shifter is needed. Power the F9P board as usual: from its own USB port, or from the ESP32 board's 5 V pin into the F9P board's 5 V input if it has one. To use other pins, change `GPS_TX_PIN` and `GPS_RX_PIN` in [platformio.ini](./platformio.ini).

Any baud rate on the module is fine. The firmware finds it and switches to 230400.

## Flash it

With [PlatformIO](https://platformio.org/) installed:

```sh
cd firmware
pio run -e esp32-s3 -t upload     # or -e esp32dev
pio device monitor
```

## Set it up

1. On first start the board creates a WiFi network called `gps-base-XXXX`, with the password `gps-base-setup`.
2. Join it and open `http://192.168.4.1`.
3. Fill in your WiFi network, the caster details and a password for the page, then save. The board restarts and joins your network.
4. Find its address in your router's device list under `gps-base`, or in the serial monitor, and open it. Log in with any user name and the page password.

If it cannot join your network for 2 minutes, the setup network comes back as well, so a changed router cannot lock it out. Holding the BOOT button for 5 seconds erases all settings.

## Using it

The page shows what it is doing, and in plain words what is wrong if anything is. All settings, and the base mode, survive a restart.

**Survey or fixed position:** corrections make a rover precise *relative to the base*, so the rover's position is only as right and as repeatable as the base's.

- **Survey** works out the position by averaging. It is quick to set up, but the default of 60 seconds and 3 m leaves the base up to metres off, and the result changes with every survey. Anything saved in rover coordinates, such as a mowing boundary, moves with it.
- **Fixed** uses a position you give it. Use this for anything that must line up from day to day. Get the position from a long survey, or from a day of raw data sent to a free service such as [OPUS](https://geodesy.noaa.gov/OPUS/) or [CSRS-PPP](https://webapp.csrs-scrs.nrcan-rncan.gc.ca/geod/tools-outils/ppp.php). Heights are above the ellipsoid, not sea level. The antenna must not move afterwards.

## Monitoring and over-the-air updates

The base reports to the [Rider monitoring service](https://rider.solvitcorp.com) over MQTT, and keeps its firmware up to date from there, the same way the solar tracker does. Both are on by default, and only need the board to be on your network.

**Reporting:** the status shown on this page goes to `mqtt.solvitcorp.com` every 5 seconds, including the base's exact position. That broker has no login yet, so anyone connecting to it could read that. To turn reporting off, empty the broker field in the settings. To use a broker with a login, fill in its user and password there.

**Automatic updates:** the board asks the service on start and every 10 minutes. If a newer release is active it installs it and restarts, which drops the corrections for under a minute. Untick the setting to install only when you press **Check for update**, or when someone asks from the service.

- It first checks that the image is this project's, and is for this chip.
- The new version has to run for a minute with a network connection. If it keeps crashing before that, the board goes back to the previous version by itself, and does not install that version again unless someone asks for it by name.
- Firmware comes over plain HTTP, like the tracker's, because an ESP32 cannot reliably hold TLS through a large download. The board checks the image is sound, but not who built it.

To publish a new version, raise `PROJECT_VER` in [CMakeLists.txt](./CMakeLists.txt), build it, and upload `.pio/build/<board>/firmware.bin` on the service's Firmware page. Each chip needs its own build, and the service holds one active release, so all base stations need the same chip.

**By hand:** the page also accepts a `firmware.bin` directly, so a board can be updated without the service.

## How it treats the caster

Public casters count failed connections per IP and ban the address, so the firmware is careful with them:

- Attempts back off from 15 seconds to 15 minutes. The delay only resets after a connection has lasted a minute.
- After a reply that says the IP is banned, it waits an hour.
- It connects only while the module is producing corrections, because a source that connects and sends nothing is dropped and counted as bad.
- It never connects with empty settings.
- Only whole frames with a valid checksum are sent, as soon as they are complete.

## First bench test

The simulator cannot check real radio, UART timing or WiFi. Before relying on this:

1. Flash it and do the setup above, with the antenna outdoors.
2. The page should go through "Looking for the GPS module" and "Surveying" to "Streaming corrections".
3. Check that your mountpoint appears in the [RTK2go status list](http://rtk2go.com:2101/SNIP::STATUS).
4. Connect a rover and confirm it reaches RTK Fixed.
5. Pull the WiFi or restart your router, and power cycle the F9P. The page should report it and recover without help each time.
6. Check that the base appears on the [monitoring service](https://rider.solvitcorp.com), on the map and with its version.
7. Upload a build with a higher version, make it active, and press **Check for update** on the page. The board should install it, restart, and report the new version. Corrections should come back by themselves.
8. Do the same with a build that crashes at start (add `abort();` to the top of `app_main`). The board should come back on the version before it, and report that it will not install that one again. **Keep USB access to the board for this test.**

## Development

The base station's logic is in [src/core](./src/core), which is portable C. The rest of `src/` connects it to the ESP32: UART, WiFi, flash, the web UI, updates ([ota.c](./src/ota.c)) and reporting ([mqtt_link.c](./src/mqtt_link.c)).

To run it on a Linux PC against a simulated module and caster:

```sh
make -C host test    # unit tests
make -C host e2e     # end-to-end scenarios, Linux only
```

These run under AddressSanitizer and exercise the same C code as the firmware, apart from the serial port, the web UI, and the MQTT and update code, which only runs on the board.
