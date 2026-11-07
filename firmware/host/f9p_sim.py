#!/usr/bin/env python3
"""
A software ZED-F9P for testing without hardware.

It answers the UBX commands sent to it on a pseudo terminal, and behaves like the module on the points that
matter: survey-in takes a few seconds, RTCM output follows UBX-CFG-MSG, and it can go silent or send damaged
frames on request. Everything it sees is kept for tests to assert on.

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
ID_CFG_PRT, ID_CFG_MSG, ID_CFG_RATE, ID_CFG_TMODE3 = 0x00, 0x01, 0x08, 0x71
ID_NAV_PVT, ID_NAV_HPPOSLLH, ID_NAV_SVIN = 0x07, 0x14, 0x3B
RTCM_MSG_CLASS = 0xF5
RTCM_TYPES = {0x05: 1005, 0x4A: 1074, 0x54: 1084, 0x5E: 1094, 0x7C: 1124}


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
    def __init__(self, survey_seconds=3.0, latitude=40.1234567, longitude=-80.1234567, height_m=300.0):
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
        self.tmode3 = bytearray(40)
        self.survey_started = None
        self.rtcm_rates = {}
        self.rate_ms = 1000
        self.port_config = None

        self.rtcm_sent_frames = []
        self.commands = []

        threading.Thread(target=self._reader, daemon=True).start()
        threading.Thread(target=self._rtcm_output, daemon=True).start()

    @property
    def mode(self):
        return self.tmode3[2]

    @property
    def fixed_position(self):
        """(lat 1e-7, lon 1e-7, height cm, lat hp, lon hp, height hp, LLA flag)"""
        lat, lon, height = struct.unpack_from("<iii", self.tmode3, 4)
        lat_hp, lon_hp, height_hp = struct.unpack_from("<bbb", self.tmode3, 16)
        return lat, lon, height, lat_hp, lon_hp, height_hp, bool(self.tmode3[3] & 1)

    @property
    def survey_settings(self):
        """(minimum seconds, accuracy limit in 0.1 mm)"""
        return struct.unpack_from("<II", self.tmode3, 24)

    def power_cycle(self):
        """Forget everything, as the module does when it loses power."""
        self.tmode3 = bytearray(40)
        self.rtcm_rates = {}
        self.survey_started = None
        self.rate_ms = 1000

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
            handler = {ID_NAV_PVT: self._nav_pvt, ID_NAV_HPPOSLLH: self._nav_hpposllh, ID_NAV_SVIN: self._nav_svin}.get(msg_id)
            if handler:
                self._write(ubx_frame(CLS_NAV, msg_id, handler()))

    def _handle_cfg(self, msg_id, payload):
        if msg_id == ID_CFG_PRT:
            if len(payload) <= 1:
                reply = bytearray(20)
                reply[0] = payload[0] if payload else 1
                self._write(ubx_frame(CLS_CFG, ID_CFG_PRT, bytes(reply)))
            else:
                self.port_config = bytes(payload)
        elif msg_id == ID_CFG_RATE:
            if len(payload) == 0:
                self._write(ubx_frame(CLS_CFG, ID_CFG_RATE, struct.pack("<HHH", self.rate_ms, 1, 1)))
            else:
                self.rate_ms = struct.unpack_from("<H", payload, 0)[0]
        elif msg_id == ID_CFG_MSG:
            if len(payload) == 2:
                self._write(ubx_frame(CLS_CFG, ID_CFG_MSG, bytes(payload) + bytes(6)))
            elif len(payload) >= 8 and payload[0] == RTCM_MSG_CLASS:
                self.rtcm_rates[payload[1]] = max(payload[2:8])
        elif msg_id == ID_CFG_TMODE3:
            if len(payload) == 0:
                self._write(ubx_frame(CLS_CFG, ID_CFG_TMODE3, bytes(self.tmode3)))
            else:
                self.tmode3 = bytearray(payload)
                self.survey_started = time.monotonic() if self.tmode3[2] == 1 else None
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
        while self.running:
            time.sleep(self.rate_ms / 1000.0)
            ready = self.mode == 2 or (self.mode == 1 and self._survey_elapsed() >= self.survey_seconds)
            if not ready:
                continue
            for key, message_type in RTCM_TYPES.items():
                if self.rtcm_rates.get(key):
                    frame = rtcm_frame(message_type)
                    if self.damage_next_frame:
                        self.damage_next_frame = False
                        self._write(frame[:10] + bytes([frame[10] ^ 0x01]) + frame[11:])
                    else:
                        self.rtcm_sent_frames.append(frame)
                        self._write(frame)
