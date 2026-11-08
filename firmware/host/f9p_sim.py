#!/usr/bin/env python3
"""
A software ZED-F9P for testing without hardware.

It answers the UBX commands sent to it on a pseudo terminal, and behaves like the module on the points that
matter: it is set up with UBX-CFG-VALSET and refuses the old CFG messages, survey-in takes a few seconds, RTCM
output follows the CFG-MSGOUT settings, and it can go silent or send damaged frames on request. Everything it sees
is kept for tests to assert on.

Linux only (uses pty). It is not a GNSS simulator: positions are constants.
"""
import os
import pty
import struct
import threading
import time
import tty

SYNC = b"\xb5\x62"
CLS_NAV, CLS_ACK, CLS_CFG = 0x01, 0x05, 0x06
ID_CFG_VALSET, ID_CFG_VALGET = 0x8A, 0x8B
# The old way of setting up a module, which u-blox no longer documents: CFG-PRT, CFG-MSG, CFG-RATE, CFG-TMODE3
LEGACY_CFG = (0x00, 0x01, 0x08, 0x71)
ID_NAV_PVT, ID_NAV_HPPOSLLH, ID_NAV_SVIN, ID_NAV_SAT, ID_NAV_SIG = 0x07, 0x14, 0x3B, 0x35, 0x43

# CFG-SIGNAL keys for each constellation: the constellation, its first band and its second band, and the u-blox
# signal numbers of those two bands
SIGNAL_KEYS = {
    0: ((0x1031001F, 0x10310001, 0x10310003), (0, 3)),  # GPS
    2: ((0x10310021, 0x10310007, 0x1031000A), (0, 5)),  # Galileo
    3: ((0x10310022, 0x1031000D, 0x1031000E), (0, 2)),  # BeiDou
    6: ((0x10310025, 0x10310018, 0x1031001A), (0, 2)),  # GLONASS
    5: ((0x10310024, 0x10310012, 0x10310015), (0, 4)),  # QZSS
}
SECOND_BAND_KEYS = [keys[2] for keys, _ in SIGNAL_KEYS.values()]

UART1_BAUDRATE = 0x40520001
UART1INPROT_UBX, UART1INPROT_NMEA, UART1INPROT_RTCM3X = 0x10730001, 0x10730002, 0x10730004
UART1OUTPROT_UBX, UART1OUTPROT_NMEA, UART1OUTPROT_RTCM3X = 0x10740001, 0x10740002, 0x10740004
RATE_MEAS, RATE_NAV, RATE_TIMEREF = 0x30210001, 0x30210002, 0x20210003
TMODE_MODE, TMODE_POS_TYPE = 0x20030001, 0x20030002
TMODE_LAT, TMODE_LON, TMODE_HEIGHT = 0x40030009, 0x4003000A, 0x4003000B
TMODE_LAT_HP, TMODE_LON_HP, TMODE_HEIGHT_HP = 0x2003000C, 0x2003000D, 0x2003000E
TMODE_SVIN_MIN_DUR, TMODE_SVIN_ACC_LIMIT = 0x40030010, 0x40030011
# The RTCM messages a base sends, by the key of their output rate on UART1
RTCM_RATE_KEYS = {1005: 0x209102BE, 1074: 0x2091035F, 1084: 0x20910364, 1094: 0x20910369, 1124: 0x2091036E, 1230: 0x20910304}
SIGNED = {TMODE_LAT, TMODE_LON, TMODE_HEIGHT, TMODE_LAT_HP, TMODE_LON_HP, TMODE_HEIGHT_HP}

# The factory settings, as a chip erase or a new module leaves them
DEFAULTS = {
    UART1_BAUDRATE: 38400,
    UART1INPROT_UBX: 1, UART1INPROT_NMEA: 1, UART1INPROT_RTCM3X: 1,
    UART1OUTPROT_UBX: 1, UART1OUTPROT_NMEA: 1, UART1OUTPROT_RTCM3X: 1,
    RATE_MEAS: 1000, RATE_NAV: 1, RATE_TIMEREF: 1,
    TMODE_MODE: 0, TMODE_POS_TYPE: 0, TMODE_LAT: 0, TMODE_LON: 0, TMODE_HEIGHT: 0,
    TMODE_LAT_HP: 0, TMODE_LON_HP: 0, TMODE_HEIGHT_HP: 0, TMODE_SVIN_MIN_DUR: 0, TMODE_SVIN_ACC_LIMIT: 0,
    **{key: 0 for key in RTCM_RATE_KEYS.values()},
    **{key: 1 for keys, _ in SIGNAL_KEYS.values() for key in keys},
}
LAYER_RAM, LAYER_FLASH = 0x01, 0x04


def value_size(key):
    """Bytes a key's value takes, from the key's own size field."""
    return {1: 1, 2: 1, 3: 2, 4: 4, 5: 8}[(key >> 28) & 7]


def unpack_value(key, data):
    return int.from_bytes(data[:value_size(key)], "little", signed=key in SIGNED)


def pack_value(key, value):
    return int(value).to_bytes(value_size(key), "little", signed=key in SIGNED)


def ubx_frame(cls, msg_id, payload=b""):
    body = bytes([cls, msg_id]) + struct.pack("<H", len(payload)) + payload
    ck_a = ck_b = 0
    for b in body:
        ck_a = (ck_a + b) & 0xFF
        ck_b = (ck_b + ck_a) & 0xFF
    return SYNC + body + bytes([ck_a, ck_b])


def crc24q(data):
    crc = 0
    for byte in data:
        crc ^= byte << 16
        for _ in range(8):
            crc <<= 1
            if crc & 0x1000000:
                crc ^= 0x1864CFB
    return crc & 0xFFFFFF


def rtcm_frame(message_type, length=60):
    """A correctly framed RTCM3 message with filler for a payload."""
    payload = struct.pack(">H", (message_type << 4) & 0xFFFF) + bytes(length - 2)
    head = b"\xd3" + struct.pack(">H", length & 0x3FF) + payload
    return head + crc24q(head).to_bytes(3, "big")


class F9pSim:
    def __init__(self, survey_seconds=3.0, latitude=40.1234567, longitude=-80.1234567, height_m=300.0, second_band=True,
                 antenna_second_band=True):
        """second_band: whether the module's saved settings track the second band. antenna_second_band: whether the
        antenna passes it, so whether anything is heard on it when it is tracked."""
        self.survey_seconds = survey_seconds
        self.latitude = latitude
        self.longitude = longitude
        self.height_m = height_m

        self.master, self.slave = pty.openpty()
        tty.setraw(self.master)
        tty.setraw(self.slave)
        self.path = os.ttyname(self.slave)

        self.lock = threading.Lock()
        self.running = True
        self.silent = False
        self.damage_next_frame = False
        self.survey_started = None

        # Settings kept through a power cut, and those in use
        self.saved = dict(DEFAULTS)
        for key in SECOND_BAND_KEYS:
            self.saved[key] = 1 if second_band else 0
        self.config = dict(self.saved)
        self.antenna_second_band = antenna_second_band
        self.refuse_flash = False
        self.valsets = []  # (layers, {key: value}) for each CFG-VALSET received

        self.rtcm_sent_frames = []
        self.commands = []

        threading.Thread(target=self._reader, daemon=True).start()
        threading.Thread(target=self._rtcm_output, daemon=True).start()

    @property
    def mode(self):
        return self.config[TMODE_MODE]

    @property
    def rate_ms(self):
        return self.config[RATE_MEAS]

    @property
    def fixed_position(self):
        """(lat 1e-7, lon 1e-7, height cm, lat hp, lon hp, height hp, LLA flag)"""
        c = self.config
        return (c[TMODE_LAT], c[TMODE_LON], c[TMODE_HEIGHT], c[TMODE_LAT_HP], c[TMODE_LON_HP], c[TMODE_HEIGHT_HP],
                c[TMODE_POS_TYPE] == 1)

    @property
    def survey_settings(self):
        """(minimum seconds, accuracy limit in 0.1 mm)"""
        return self.config[TMODE_SVIN_MIN_DUR], self.config[TMODE_SVIN_ACC_LIMIT]

    def power_cycle(self):
        """Forget everything not saved, as the module does when it loses power."""
        self.config = dict(self.saved)
        self.survey_started = None

    def close(self):
        self.running = False
        for fd in (self.master, self.slave):
            try:
                os.close(fd)
            except OSError:
                pass

    def _write(self, data):
        if self.silent:
            return
        try:
            with self.lock:
                os.write(self.master, data)
        except OSError:
            pass

    def _reader(self):
        buffer = bytearray()
        while self.running:
            try:
                chunk = os.read(self.master, 4096)
            except OSError:
                return
            buffer.extend(chunk)
            self._parse(buffer)

    def _parse(self, buffer):
        while buffer:
            if buffer[0] != 0xB5:
                del buffer[0]
                continue
            if len(buffer) < 6:
                return
            length = struct.unpack_from("<H", buffer, 4)[0]
            if len(buffer) < 8 + length:
                return
            frame = bytes(buffer[: 8 + length])
            del buffer[: 8 + length]
            if frame == ubx_frame(frame[2], frame[3], frame[6:-2]):
                self._handle_ubx(frame[2], frame[3], frame[6:-2])

    def _handle_ubx(self, cls, msg_id, payload):
        if self.silent:
            return
        self.commands.append((cls, msg_id, bytes(payload)))

        if cls == CLS_CFG:
            self._handle_cfg(msg_id, payload)
        elif cls == CLS_NAV:
            handler = {ID_NAV_PVT: self._nav_pvt, ID_NAV_HPPOSLLH: self._nav_hpposllh, ID_NAV_SVIN: self._nav_svin,
                       ID_NAV_SAT: self._nav_sat, ID_NAV_SIG: self._nav_sig}.get(msg_id)
            if handler:
                self._write(ubx_frame(CLS_NAV, msg_id, handler()))

    def _refuse(self, msg_id):
        self._write(ubx_frame(CLS_ACK, 0x00, bytes([CLS_CFG, msg_id])))

    def _handle_cfg(self, msg_id, payload):
        if msg_id == ID_CFG_VALGET:
            keys = [struct.unpack_from("<I", payload, at)[0] for at in range(4, len(payload) - 3, 4)]
            if any(key not in self.config for key in keys):
                # One key it does not know and the whole question is refused
                return self._refuse(msg_id)
            answer = bytes([1, payload[1], 0, 0]) + b"".join(struct.pack("<I", key) + pack_value(key, self.config[key]) for key in keys)
            self._write(ubx_frame(CLS_CFG, ID_CFG_VALGET, answer))
        elif msg_id == ID_CFG_VALSET:
            layers = payload[1]
            changes = {}
            at = 4
            while at + 4 <= len(payload):
                key = struct.unpack_from("<I", payload, at)[0]
                if key not in self.config or at + 4 + value_size(key) > len(payload):
                    # All or nothing: one key it does not know and nothing changes
                    return self._refuse(msg_id)
                changes[key] = unpack_value(key, payload[at + 4:])
                at += 4 + value_size(key)
            self.valsets.append((layers, changes))
            if self.refuse_flash and layers & LAYER_FLASH:
                return self._refuse(msg_id)
            if layers & LAYER_RAM:
                self.config.update(changes)
                if TMODE_MODE in changes:
                    self.survey_started = time.monotonic() if changes[TMODE_MODE] == 1 else None
            if layers & LAYER_FLASH:
                self.saved.update(changes)
        else:
            # Includes the old messages, CFG-PRT, CFG-MSG, CFG-RATE and CFG-TMODE3, as if the module had dropped them
            return self._refuse(msg_id)
        self._write(ubx_frame(CLS_ACK, 0x01, bytes([CLS_CFG, msg_id])))

    def _nav_pvt(self):
        message = bytearray(92)
        message[20] = 3  # 3D fix
        message[23] = 24  # satellites
        struct.pack_into("<ii", message, 24, int(self.longitude * 1e7), int(self.latitude * 1e7))
        struct.pack_into("<ii", message, 32, int(self.height_m * 1000), int((self.height_m - 34) * 1000))
        return bytes(message)

    def _nav_hpposllh(self):
        message = bytearray(36)
        struct.pack_into("<ii", message, 8, int(self.longitude * 1e7), int(self.latitude * 1e7))
        struct.pack_into("<ii", message, 16, int(self.height_m * 1000), int((self.height_m - 34) * 1000))
        struct.pack_into("<I", message, 28, 14000)  # 1.4 m in 0.1 mm
        return bytes(message)

    def _nav_sat(self):
        """32 satellites over four constellations: more than the old 256-byte limit on a message."""
        count = 32
        message = bytearray(8 + 12 * count)
        message[4], message[5] = 1, count
        for i in range(count):
            gnss = (0, 2, 3, 6)[i % 4]
            struct.pack_into("<BBBbhhI", message, 8 + 12 * i, gnss, i + 1, 30 + i % 20, 10 + (i * 7) % 80, (i * 37) % 360, 0,
                             0x08 if i % 3 else 0)
        return bytes(message)

    def _nav_sig(self):
        """Six satellites of each of four constellations on the first band, and on the second where it is tracked and
        the antenna passes it, with an SBAS signal and one searched for but not heard."""
        signals = []
        for gnss in (0, 2, 3, 6):
            (on, first, second), (first_id, second_id) = SIGNAL_KEYS[gnss]
            if not self.config[on]:
                continue
            for sv in range(1, 7):
                if self.config[first]:
                    signals.append((gnss, sv, first_id, 38 + sv, 0x08 | 0x10))
                if self.config[second] and self.antenna_second_band:
                    signals.append((gnss, sv, second_id, 30 + sv, 0x10))
        signals.append((1, 133, 0, 30, 0))
        signals.append((0, 30, 0, 0, 0))
        message = bytearray(8 + 16 * len(signals))
        message[4], message[5] = 0, len(signals)
        for i, (gnss, sv, sig, cno, flags) in enumerate(signals):
            struct.pack_into("<BBBBhBBBBH", message, 8 + 16 * i, gnss, sv, sig, 0, 0, cno, 7, 0, 0, flags)
        return bytes(message)

    def _survey_elapsed(self):
        return 0.0 if self.survey_started is None else time.monotonic() - self.survey_started

    def _nav_svin(self):
        message = bytearray(40)
        struct.pack_into("<I", message, 8, int(self._survey_elapsed()))
        struct.pack_into("<I", message, 28, 25000)  # 2.5 m
        done = self.survey_started is not None and self._survey_elapsed() >= self.survey_seconds
        message[36] = 1 if done else 0
        message[37] = 0 if done else 1
        return bytes(message)

    def _rtcm_output(self):
        epoch = 0
        while self.running:
            time.sleep(self.rate_ms / 1000.0)
            epoch += 1
            ready = self.mode == 2 or (self.mode == 1 and self._survey_elapsed() >= self.survey_seconds)
            if not ready:
                continue
            for message_type, key in RTCM_RATE_KEYS.items():
                rate = self.config[key]
                if rate and epoch % rate == 0:
                    frame = rtcm_frame(message_type)
                    if self.damage_next_frame:
                        self.damage_next_frame = False
                        self._write(frame[:10] + bytes([frame[10] ^ 0x01]) + frame[11:])
                    else:
                        self.rtcm_sent_frames.append(frame)
                        self._write(frame)
