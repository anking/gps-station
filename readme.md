# RTK GPS Base Station

A **u-blox ZED-F9P RTK GPS receiver** broadcasting **RTCM correction data** to an **NTRIP caster** (such as **RTK2go** or any SNIP service), providing the corrections for [gps-rider](https://github.com/anking/gps-rider) and other rovers.

**The base station now runs on an ESP32. See [firmware/](./firmware).** It needs no Raspberry Pi, .NET or Node.js, and does everything the Pi did except drive a screen on the device itself.

The rest of this page describes the original Raspberry Pi application. It stays only until the firmware has passed its [first bench test](./firmware/readme.md#first-bench-test) on real hardware, and should then be removed along with its dependency on the [zedf9p-server](https://github.com/anking/zedf9p-server) driver.

# Raspberry Pi application

## Features
- **NTRIP Server**: Streams GPS correction data to an NTRIP caster, and recovers by itself from caster and module problems.
- **Web UI**: Displays real-time location on a map and receiver status, behind a password.
- **Mode Control**: Switches between **Survey** and **Fixed** modes. The chosen mode survives a restart.
- **USB Connection**: Uses the [zedf9p-server](https://github.com/anking/zedf9p-server) driver to communicate with the ZED-F9P.

## Installation

You need a Raspberry Pi 3 or above running Raspberry Pi OS, 64-bit recommended, and a [mountpoint reservation on RTK2go](http://rtk2go.com/sample-page/new-reservation/).

```sh
curl -fsSLO https://raw.githubusercontent.com/anking/gps-station/main/install.sh
bash install.sh
```

The script works for any user name. It installs Node.js (24 on 64-bit, 22 on 32-bit), clones this repository into `~/gps-station`, downloads the driver for your processor, asks for your mountpoint and password, generates a web UI password and starts the service. Run it again to update.

After starting, the UI is at `http://<your Pi>:3000`. Log in with any user name and the password from `.env`.

### Manual installation

```sh
git clone https://github.com/anking/gps-station.git
cd gps-station
cp .env.example .env    # then fill it in
npm install
npm run build
```

Put the [driver for your processor](https://github.com/anking/zedf9p-server/releases/latest/) in `f9p/`, so that it runs as `f9p/Zedf9p`, then:

```sh
npm start
```

## Configuration

Everything is set in `.env`; see [.env.example](./.env.example).

**Web UI password:** without `UI_PASSWORD`, the UI is served only to the Pi itself. The UI can move the base and switch the machine off, so it never goes on the network unprotected. A screen on the Pi itself never asks for the password.

**Screen on the Pi:** the app opens Chromium in kiosk mode if it finds it. Set `KIOSK_BROWSER=false` on a Pi with no screen. See the [Touchscreen README](./touchscreen/readme.md) for a 3.5" display.

## Survey or fixed position

Corrections make a rover precise *relative to the base*, so the rover's position is only as right, and as repeatable, as the base's.

- **Survey mode** works out the position by averaging. It is quick to set up, but the default of 60 seconds and 3 m leaves the base up to metres off, and the result changes with every survey. Anything saved in rover coordinates, such as a mowing boundary, moves with it.
- **Fixed mode** uses a position you give it. Use this for anything that must line up from day to day.

To get a position, run a long survey, or log raw data for a day and submit it to a free service such as [OPUS](https://geodesy.noaa.gov/OPUS/) or [CSRS-PPP](https://webapp.csrs-scrs.nrcan-rncan.gc.ca/geod/tools-outils/ppp.php). Then enter it in the UI, or set `BASE_FIXED_POSITION` in `.env`.

Heights are **above the ellipsoid**, not above sea level. The height the UI shows is already above the ellipsoid.

The base's antenna must not move after this.

## Running as a service

`install.sh` sets this up.

```sh
sudo systemctl status gpsstationweb
sudo systemctl restart gpsstationweb
journalctl -u gpsstationweb
```

## Errors shown in the UI

| Flag | Meaning |
| --- | --- |
| `NTRIP_NOT_CONFIGURED` | The caster settings in `.env` are not filled in, so nothing connects. |
| `NTRIP_CONNECTION_ERROR` | The caster cannot be reached, or refused the connection. It retries with a growing delay, up to 15 minutes. |
| `NTRIP_BANNED` | The caster says this IP is banned. It waits an hour between attempts. |
| `RTCM_OUTPUT_STALLED` | The module stopped producing corrections, so it stays off the caster until they return. |
| `GPS_NOT_CONNECTED` | No ZED-F9P on USB. It keeps looking. |
| `GPS_CONNECTION_ERROR`, `GPS_NO_DATA` | The module is not answering. |
| `INVALID_FIXED_POSITION` | A position was refused. The base carries on as it was. |
| `DRIVER_CONFIG_ERROR` | The driver refused its settings. Check `.env` and restart the service. |
| `DRIVER_RESTARTING` | The driver stopped and is about to restart. |

## Development

```sh
npm test
```

## F9P Device Driver Bypass / Using Str2Str
Alternatively, you can use `str2str` to transfer the F9P data directly to the caster.
This service connects directly to the F9P serial port and transfers all the data it produces to the caster. You have to configure the module yourself.
For this, use `location-streamer.service`. More info is available in [str2str-service/readme_old.txt](./str2str-service/readme_old.txt).
