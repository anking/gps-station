#!/usr/bin/env python3
"""
End-to-end checks of the base station core against a software ZED-F9P and a fake NTRIP caster, on a PC.

    make -C firmware/host e2e

These run the same C code as the firmware, apart from the serial port and the web UI.
"""
import json
import os
import socket
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from f9p_sim import ID_CFG_VALSET, SECOND_BAND_KEYS, F9pSim, crc24q  # noqa: E402

HOST = None
RESULTS = {}


class Caster:
    """Answers NTRIP handshakes the way a scenario asks and records what it received."""

    def __init__(self, reply=b"ICY 200 OK\r\n"):
        self.reply = reply
        self.requests = []
        self.received = bytearray()
        self.connections = []
        self.closed = 0
        self.attempt_times = []
        self.server = socket.create_server(("127.0.0.1", 0))
        self.port = self.server.getsockname()[1]
        self.running = True
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self):
        while self.running:
            try:
                conn, _ = self.server.accept()
            except OSError:
                return
            threading.Thread(target=self._serve, args=(conn,), daemon=True).start()

    def _serve(self, conn):
        self.attempt_times.append(time.monotonic())
        data = b""
        while b"\r\n\r\n" not in data:
            try:
                chunk = conn.recv(4096)
            except OSError:
                return
            if not chunk:
                return
            data += chunk
        head, _, rest = data.partition(b"\r\n\r\n")
        self.requests.append(head.decode("ascii", "replace") + "\r\n\r\n")
        conn.sendall(self.reply)
        if not self.reply.startswith(b"ICY"):
            conn.close()
            return
        self.connections.append(conn)
        self.received.extend(rest)
        try:
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                self.received.extend(chunk)
        except OSError:
            pass
        self.closed += 1

    def drop_all(self):
        for conn in self.connections:
            try:
                conn.shutdown(socket.SHUT_RDWR)
                conn.close()
            except OSError:
                pass
        self.connections.clear()

    def close(self):
        self.running = False
        self.server.close()
        self.drop_all()


def free_port():
    with socket.create_server(("127.0.0.1", 0)) as server:
        return server.getsockname()[1]


class Rover:
    """Connects to the base directly, the way the mower does, and keeps what it receives."""

    def __init__(self, port, request=b"GET /base HTTP/1.0\r\nUser-Agent: NTRIP test\r\nAccept: */*\r\nConnection: close\r\n\r\n"):
        deadline = time.monotonic() + 10
        while True:
            try:
                self.sock = socket.create_connection(("127.0.0.1", port), timeout=5)
                break
            except OSError:
                if time.monotonic() > deadline:
                    raise
                time.sleep(0.1)
        self.received = bytearray()
        self.hung_up = False
        if request:
            self.sock.sendall(request)
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        self.sock.settimeout(None)
        try:
            while True:
                chunk = self.sock.recv(4096)
                if not chunk:
                    break
                self.received.extend(chunk)
        except OSError:
            pass
        self.hung_up = True

    @property
    def stream(self):
        return bytes(self.received)[len(STREAM_REPLY):]

    def close(self):
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.sock.close()


STREAM_REPLY = b"ICY 200 OK\r\n\r\n"


def complete_frames(data):
    """The part of data that ends on a frame boundary, because a read can stop part way through a frame."""
    data = bytes(data)
    end = 0
    while end + 3 <= len(data):
        frame_end = end + (((data[end + 1] & 3) << 8) | data[end + 2]) + 6
        if frame_end > len(data):
            break
        end = frame_end
    return data[:end]


class Base:
    def __init__(self, sim, caster, *args):
        self.lines = []
        self.errors = []
        self.signals = {}
        self.process = subprocess.Popen(
            [HOST, "--serial", sim.path, "--host", "127.0.0.1", "--port", str(caster.port), "--mount", "TEST", "--password", "secret", *args],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
        threading.Thread(target=self._read_status, daemon=True).start()
        threading.Thread(target=self._read_errors, daemon=True).start()

    def _read_status(self):
        for line in self.process.stdout:
            if line.startswith("SIGNALS "):
                self.signals = json.loads(line[len("SIGNALS "):])
            else:
                self.lines.append(json.loads(line))

    def _read_errors(self):
        for line in self.process.stderr:
            self.errors.append(line)

    @property
    def status(self):
        return self.lines[-1] if self.lines else {}

    def send(self, command):
        self.process.stdin.write(command + "\n")
        self.process.stdin.flush()

    def stop(self):
        if sys.exc_info()[0] is not None:
            print(f"--- last status: {self.status}\n--- stderr: {''.join(self.errors)[-1500:]}", flush=True)
        self.process.kill()
        self.process.wait()


def wait_for(condition, timeout, what):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(0.05)
    raise AssertionError(f"timed out after {timeout}s waiting for {what}")


def check(condition, what):
    if not condition:
        raise AssertionError(what)


def whole_frames(data):
    """True when data is an unbroken run of complete RTCM3 frames with correct CRCs."""
    data = bytes(data)
    i = 0
    while i < len(data):
        if data[i] != 0xD3 or i + 3 > len(data):
            return False
        end = i + (((data[i + 1] & 3) << 8) | data[i + 2]) + 6
        if end > len(data) or crc24q(data[i:end - 3]) != int.from_bytes(data[end - 3:end], "big"):
            return False
        i = end
    return True


# Scenarios ----------------------------------------------------------------------------------------

def survey_then_upload():
    caster, sim = Caster(), F9pSim(survey_seconds=2)
    base = Base(sim, caster, "--survey", "3000:2")
    try:
        wait_for(lambda: base.status.get("phase") == "surveying", 10, "survey to start")
        check(sim.survey_settings == (2, 30000), f"survey settings on the module: {sim.survey_settings}")
        wait_for(lambda: base.status.get("survey_elapsed_s", 0) >= 1, 5, "survey progress")
        check(base.status["survey_accuracy_m"] == 2.5, f"survey accuracy {base.status}")
        check(len(caster.attempt_times) == 0, "must not connect before corrections flow")
        wait_for(lambda: len(caster.requests) == 1, 15, "caster connection after the survey")
        check(caster.requests[0].startswith("SOURCE secret /TEST\r\n"), f"bad login: {caster.requests[0]!r}")
        wait_for(lambda: len(caster.received) >= 400, 10, "corrections at the caster")
        check(whole_frames(caster.received), "the caster must receive whole, valid frames")
        check(sim.rate_ms == 1000, f"base should run at 1 Hz, got {sim.rate_ms} ms")
        check(sim.port_config[14] == 0x21, "UART1 output must be UBX and RTCM only")
        check(any(c[0] == 0x01 and c[1] == 0x35 for c in sim.commands), "the satellite list must be asked for")
        wait_for(lambda: base.status.get("have_position"), 5, "position")
        check(abs(base.status["lat"] - 40.1234567) < 1e-6, f"latitude {base.status}")
        check(base.status["height_m"] == 300.0, f"height in meters {base.status}")
        check(base.status["height_msl_m"] == 266.0, f"height above sea level {base.status}")
        check(base.status["accuracy_m"] == 1.4, f"accuracy in meters {base.status}")
        check(base.status["satellites"] == 24, f"satellites {base.status}")
        check(base.status["caster_connected"] is True, f"connected {base.status}")
        check(base.status["errors"] == [], f"errors {base.status}")
        check(0 <= base.status["sent_age_ms"] < 3000, f"sent age {base.status}")
    finally:
        base.stop(), sim.close(), caster.close()


def fixed_from_start_skips_the_survey():
    caster, sim = Caster(), F9pSim(survey_seconds=999)
    base = Base(sim, caster, "--fixed", "-33.8688000:151.2093000:58.5")
    try:
        wait_for(lambda: sim.mode == 2, 5, "fixed mode")
        lat, lon, height, _, _, _, lla = sim.fixed_position
        check((lat, lon, height, lla) == (-338688000, 1512093000, 5850, True), f"position {sim.fixed_position}")
        wait_for(lambda: len(caster.received) > 200, 10, "corrections without a survey")
        check(whole_frames(caster.received), "whole frames")
        check(all(c[1] != 0x3B for c in sim.commands), "fixed mode must not poll the survey")
        check(base.status["mode"] == "fixed", f"mode {base.status}")
    finally:
        base.stop(), sim.close(), caster.close()


def switch_to_fixed_while_running():
    caster, sim = Caster(), F9pSim(survey_seconds=1)
    base = Base(sim, caster, "--survey", "3000:1")
    try:
        wait_for(lambda: len(caster.received) > 0, 15, "corrections before the change")
        # A trailing zero and a negative longitude: the old parser turned these into the wrong place
        base.send("FIXED 40.1234560 -80.1234567 300.25")
        wait_for(lambda: sim.mode == 2, 5, "fixed mode on the module")
        check(sim.fixed_position[:3] == (401234560, -801234567, 30025), f"position {sim.fixed_position}")
        # The old connection must close first or the caster reports the mountpoint as taken
        wait_for(lambda: caster.closed == 1, 5, "old connection closed")
        wait_for(lambda: len(caster.requests) == 2, 10, "reconnect at once")
        before = len(caster.received)
        wait_for(lambda: len(caster.received) > before + 200, 10, "corrections in fixed mode")

        base.send("SURVEY 2000 1")
        wait_for(lambda: sim.mode == 1, 5, "back to survey")
        check(sim.survey_settings == (1, 20000), f"new survey settings {sim.survey_settings}")
        wait_for(lambda: len(caster.requests) == 3, 15, "reconnect after the survey")
    finally:
        base.stop(), sim.close(), caster.close()


def bad_position_changes_nothing():
    caster, sim = Caster(), F9pSim(survey_seconds=1)
    base = Base(sim, caster, "--survey", "3000:1")
    try:
        wait_for(lambda: len(caster.received) > 0, 15, "corrections")
        base.send("FIXED 95.0 10.0 300")
        wait_for(lambda: "INVALID_FIXED_POSITION" in base.status.get("errors", []), 3, "error shown")
        check(sim.mode == 1, "the module must not be touched")
        check(len(caster.requests) == 1, "the connection must not be touched")
        before = len(caster.received)
        wait_for(lambda: len(caster.received) > before + 200, 10, "corrections carrying on")
    finally:
        base.stop(), sim.close(), caster.close()


def reconnects_after_a_drop_without_resurveying():
    caster, sim = Caster(), F9pSim(survey_seconds=1)
    base = Base(sim, caster, "--survey", "3000:1")
    try:
        wait_for(lambda: len(caster.received) > 0, 15, "first connection")
        svin_polls = sum(1 for c in sim.commands if c[1] == 0x3B)
        caster.drop_all()
        wait_for(lambda: "NTRIP_CONNECTION_ERROR" in base.status.get("errors", []), 5, "error after the drop")
        time.sleep(5)
        check(len(caster.attempt_times) == 1, "must wait before reconnecting")
        wait_for(lambda: len(caster.requests) == 2, 15, "reconnect")
        before = len(caster.received)
        wait_for(lambda: len(caster.received) > before + 200, 10, "corrections after the reconnect")
        check(sum(1 for c in sim.commands if c[1] == 0x3B) == svin_polls, "a caster drop must not restart the survey")
        wait_for(lambda: base.status.get("errors") == [], 3, "error cleared")
    finally:
        base.stop(), sim.close(), caster.close()


def backs_off_when_refused():
    caster, sim = Caster(reply=b"ERROR - Bad Password\r\n"), F9pSim(survey_seconds=1)
    base = Base(sim, caster, "--survey", "3000:1")
    try:
        wait_for(lambda: len(caster.attempt_times) == 2, 30, "second attempt")
        gap = caster.attempt_times[1] - caster.attempt_times[0]
        check(gap >= 14, f"retry too fast: {gap:.1f}s")
        check(base.status["caster_message"] == "ERROR - Bad Password", f"reason shown {base.status}")
        check("NTRIP_CONNECTION_ERROR" in base.status["errors"], f"errors {base.status}")
        time.sleep(5)
        check(len(caster.attempt_times) == 2, "the wait must grow")
    finally:
        base.stop(), sim.close(), caster.close()


def stops_retrying_when_banned():
    caster, sim = Caster(reply=b"HTTP/1.1 403 Forbidden\r\n\r\nYour IP has been banned\r\n"), F9pSim(survey_seconds=1)
    base = Base(sim, caster, "--survey", "3000:1")
    try:
        wait_for(lambda: "NTRIP_BANNED" in base.status.get("errors", []), 15, "banned flag")
        time.sleep(20)
        check(len(caster.attempt_times) == 1, f"must not retry while banned, saw {len(caster.attempt_times)}")
    finally:
        base.stop(), sim.close(), caster.close()


def damaged_frames_never_reach_the_caster():
    caster, sim = Caster(), F9pSim(survey_seconds=1)
    base = Base(sim, caster, "--survey", "3000:1")
    try:
        wait_for(lambda: len(caster.received) > 0, 15, "corrections")
        sim.damage_next_frame = True
        wait_for(lambda: base.status.get("rtcm_errors") == 1, 5, "damaged frame counted")
        before = len(caster.received)
        wait_for(lambda: len(caster.received) > before + 300, 10, "corrections carrying on")
        check(whole_frames(caster.received), "only valid frames at the caster")
    finally:
        base.stop(), sim.close(), caster.close()


def recovers_from_a_module_power_cycle():
    caster, sim = Caster(), F9pSim(survey_seconds=1)
    base = Base(sim, caster, "--survey", "3000:1")
    try:
        wait_for(lambda: len(caster.received) > 0, 15, "corrections")
        sim.silent = True
        sim.power_cycle()
        wait_for(lambda: base.status.get("phase") == "finding_module", 10, "noticing the silence")
        check(base.status["caster_connected"] is False, "stop streaming")
        time.sleep(1)
        sim.silent = False
        wait_for(lambda: sim.mode == 1, 15, "reconfigured")
        before = len(caster.received)
        wait_for(lambda: len(caster.received) > before + 200, 45, "corrections again")
    finally:
        base.stop(), sim.close(), caster.close()


def stays_off_the_caster_while_the_module_is_silent():
    caster, sim = Caster(), F9pSim()
    sim.silent = True
    base = Base(sim, caster)
    try:
        wait_for(lambda: "GPS_NOT_CONNECTED" in base.status.get("errors", []), 10, "module not found")
        check(len(caster.attempt_times) == 0, "must not connect")
    finally:
        base.stop(), sim.close(), caster.close()


def waits_for_the_network():
    open("/tmp/base-network-down", "w").close()
    caster, sim = Caster(), F9pSim(survey_seconds=1)
    base = Base(sim, caster, "--survey", "3000:1")
    try:
        wait_for(lambda: "NETWORK_DOWN" in base.status.get("errors", []), 15, "network error")
        time.sleep(1)
        check(len(caster.attempt_times) == 0, "must not connect")
        os.remove("/tmp/base-network-down")
        wait_for(lambda: len(caster.received) > 0, 10, "corrections once the network is back")
    finally:
        base.stop(), sim.close(), caster.close()
        if os.path.exists("/tmp/base-network-down"):
            os.remove("/tmp/base-network-down")


def unconfigured_never_connects():
    caster, sim = Caster(), F9pSim(survey_seconds=1)
    process = subprocess.Popen([HOST, "--serial", sim.path, "--host", "127.0.0.1", "--port", str(caster.port), "--mount", "", "--password", ""],
                               stdout=subprocess.PIPE, text=True)
    try:
        line = process.stdout.readline()
        check("NTRIP_NOT_CONFIGURED" in line, f"status {line}")
        time.sleep(2)
        check(len(caster.attempt_times) == 0, "must not connect")
    finally:
        process.kill(), process.wait(), sim.close(), caster.close()


def rover_gets_whole_frames_alongside_the_caster():
    caster, sim, port = Caster(), F9pSim(survey_seconds=1), free_port()
    base = Base(sim, caster, "--survey", "3000:1", "--direct-port", str(port))
    rover = Rover(port)
    try:
        wait_for(lambda: bytes(rover.received).startswith(STREAM_REPLY), 5, "the reply to the rover")
        wait_for(lambda: base.status.get("direct_rovers") == 1, 3, "the rover in the status")
        check(base.status["direct_port"] == port, f"port in the status {base.status}")
        wait_for(lambda: len(rover.stream) > 400, 15, "corrections at the rover")
        wait_for(lambda: len(caster.received) > 400, 10, "corrections at the caster as well")
        frames = complete_frames(rover.stream)
        check(len(frames) > 0 and whole_frames(frames), "the rover must receive whole, valid frames")
        check(base.status["errors"] == [], f"errors {base.status}")

        rover.close()
        wait_for(lambda: base.status.get("direct_rovers") == 0, 3, "the rover leaving")
        before = len(caster.received)
        wait_for(lambda: len(caster.received) > before + 200, 10, "the caster unaffected")

        again = Rover(port)
        wait_for(lambda: len(again.stream) > 200, 10, "a rover coming back")
        again.close()
    finally:
        rover.close(), base.stop(), sim.close(), caster.close()


def rover_is_served_with_no_caster_set_up():
    caster, sim, port = Caster(), F9pSim(survey_seconds=1), free_port()
    process = subprocess.Popen([HOST, "--serial", sim.path, "--host", "127.0.0.1", "--port", str(caster.port), "--mount", "", "--password", "",
                                "--survey", "3000:1", "--direct-port", str(port)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    rover = Rover(port)
    try:
        wait_for(lambda: len(rover.stream) > 400, 15, "corrections at the rover")
        frames = complete_frames(rover.stream)
        check(len(frames) > 0 and whole_frames(frames), "whole frames")
        check(len(caster.attempt_times) == 0, "must not connect to the caster")
    finally:
        rover.close(), process.kill(), process.wait(), sim.close(), caster.close()


def rover_carries_on_when_the_caster_refuses():
    caster, sim, port = Caster(reply=b"ERROR - Bad Password\r\n"), F9pSim(survey_seconds=1), free_port()
    base = Base(sim, caster, "--survey", "3000:1", "--direct-port", str(port))
    rover = Rover(port)
    try:
        wait_for(lambda: "NTRIP_CONNECTION_ERROR" in base.status.get("errors", []), 15, "the caster refusing")
        before = len(rover.stream)
        wait_for(lambda: len(rover.stream) > before + 300, 10, "corrections at the rover regardless")
        check(base.status["direct_rovers"] == 1, f"still connected {base.status}")
    finally:
        rover.close(), base.stop(), sim.close(), caster.close()


def rover_stays_connected_through_a_module_power_cycle():
    caster, sim, port = Caster(), F9pSim(survey_seconds=1), free_port()
    base = Base(sim, caster, "--survey", "3000:1", "--direct-port", str(port))
    rover = Rover(port)
    try:
        wait_for(lambda: len(rover.stream) > 0, 15, "corrections")
        sim.silent = True
        sim.power_cycle()
        wait_for(lambda: base.status.get("phase") == "finding_module", 10, "noticing the silence")
        check(not rover.hung_up, "the rover's connection has done nothing wrong")
        sim.silent = False
        before = len(rover.stream)
        wait_for(lambda: len(rover.stream) > before + 200, 45, "corrections again, with no reconnect")
    finally:
        rover.close(), base.stop(), sim.close(), caster.close()


def a_new_rover_takes_the_place_of_the_oldest():
    caster, sim, port = Caster(), F9pSim(survey_seconds=1), free_port()
    base = Base(sim, caster, "--survey", "3000:1", "--direct-port", str(port))
    first = Rover(port)
    second, third = None, None
    try:
        wait_for(lambda: base.status.get("direct_rovers") == 1, 5, "the first rover")
        time.sleep(0.1)
        second = Rover(port)
        wait_for(lambda: base.status.get("direct_rovers") == 2, 5, "the second rover")
        time.sleep(0.1)
        third = Rover(port)
        wait_for(lambda: first.hung_up, 5, "the oldest rover dropped")
        wait_for(lambda: bytes(third.received).startswith(STREAM_REPLY), 5, "the newest rover answered")
        check(not second.hung_up, "only the oldest goes")
    finally:
        for rover in (first, second, third):
            if rover:
                rover.close()
        base.stop(), sim.close(), caster.close()


def anything_else_is_turned_away():
    caster, sim, port = Caster(), F9pSim(survey_seconds=1), free_port()
    base = Base(sim, caster, "--survey", "3000:1", "--direct-port", str(port))
    rovers = []
    try:
        # One at a time, because a new connection can take the place of the oldest
        for request, reply in ((b"GET / HTTP/1.0\r\n\r\n", b"HTTP/1.0 400"), (b"SOURCE secret /base\r\n\r\n", b"HTTP/1.0 400"), (b"X" * 400, b"")):
            rover = Rover(port, request=request)
            rovers.append(rover)
            wait_for(lambda: rover.hung_up, 5, f"{request[:20]!r} closed")
            check(bytes(rover.received).startswith(reply), f"reply to {request[:20]!r}: {bytes(rover.received)!r}")
            check(STREAM_REPLY not in bytes(rover.received), "no corrections for it")
        silent = Rover(port, request=b"")
        rovers.append(silent)
        wait_for(lambda: silent.hung_up, 10, "a connection that says nothing closed")
        check(not silent.received, "nothing sent before it asks")
        check(base.status.get("direct_rovers") == 0, f"status {base.status}")
    finally:
        for rover in rovers:
            rover.close()
        base.stop(), sim.close(), caster.close()


def turns_the_second_band_on():
    # As found on the real base: a module set to L1 only, so the corrections carried nothing else
    caster, sim = Caster(), F9pSim(survey_seconds=1, second_band=False)
    base = Base(sim, caster, "--survey", "3000:1")
    try:
        wait_for(lambda: base.signals.get("second_band") == "off", 15, "the band settings read")
        check(base.signals["settings"][0] == [0, 1, 1, 0], f"GPS settings {base.signals['settings']}")
        wait_for(lambda: "SINGLE_BAND" in base.status.get("errors", []), 30, "the single band warning")
        check(base.status["bands"]["second"] == "off", f"bands {base.status['bands']}")
        check(base.status["bands"]["l1"] == [24, 24, 42] and base.status["bands"]["l2"] == [0, 0, 0], f"bands {base.status['bands']}")
        check(base.signals["request"] == "none", f"request {base.signals}")

        before = len(caster.received)
        base.send("SECOND_BAND")
        wait_for(lambda: base.signals.get("request") == "saved", 8, "the module saving it")
        check(sim.valset_layers == [0x07], f"layers {sim.valset_layers}")
        check(all(sim.saved_signals[key] == 1 for key in SECOND_BAND_KEYS), "kept through a power cut")
        wait_for(lambda: base.signals.get("second_band") == "on", 8, "the settings read again")
        wait_for(lambda: "SINGLE_BAND" not in base.status.get("errors", []), 10, "the warning gone")
        check(base.status["bands"]["l2"][0] == 24, f"second band heard {base.status['bands']}")
        # The list is printed less often than the status
        wait_for(lambda: any(s[2] == 2 for s in base.signals["signals"]), 5, "second band signals in the list")
        wait_for(lambda: len(caster.received) > before + 300, 10, "corrections carrying on")
    finally:
        base.stop(), sim.close(), caster.close()


def second_band_on_until_power_off_when_the_module_will_not_save_it():
    caster, sim = Caster(), F9pSim(survey_seconds=1, second_band=False)
    sim.refuse_flash = True
    base = Base(sim, caster, "--survey", "3000:1")
    try:
        wait_for(lambda: base.signals.get("second_band") == "off", 15, "the band settings read")
        base.send("SECOND_BAND")
        wait_for(lambda: base.signals.get("request") == "on_until_power_off", 8, "the module taking it for now")
        check(sim.valset_layers == [0x07, 0x01], f"layers {sim.valset_layers}")
        check(all(sim.signals[key] == 1 for key in SECOND_BAND_KEYS), "on in use")
        check(all(sim.saved_signals[key] == 0 for key in SECOND_BAND_KEYS), "not saved")
        wait_for(lambda: base.signals.get("second_band") == "on", 8, "the settings read again")
    finally:
        base.stop(), sim.close(), caster.close()


def an_antenna_for_l1_only_still_warns():
    # The setting is right, but nothing comes through on the second band
    caster, sim = Caster(), F9pSim(survey_seconds=1, antenna_second_band=False)
    base = Base(sim, caster, "--survey", "3000:1")
    try:
        wait_for(lambda: base.signals.get("second_band") == "on", 15, "the band settings read")
        wait_for(lambda: "SINGLE_BAND" in base.status.get("errors", []), 30, "the single band warning")
        check(not any(c[1] == ID_CFG_VALSET for c in sim.commands), "nothing changed on the module by itself")
    finally:
        base.stop(), sim.close(), caster.close()


SCENARIOS = [
    turns_the_second_band_on,
    second_band_on_until_power_off_when_the_module_will_not_save_it,
    an_antenna_for_l1_only_still_warns,
    rover_gets_whole_frames_alongside_the_caster,
    rover_is_served_with_no_caster_set_up,
    rover_carries_on_when_the_caster_refuses,
    rover_stays_connected_through_a_module_power_cycle,
    a_new_rover_takes_the_place_of_the_oldest,
    anything_else_is_turned_away,
    survey_then_upload,
    fixed_from_start_skips_the_survey,
    switch_to_fixed_while_running,
    bad_position_changes_nothing,
    reconnects_after_a_drop_without_resurveying,
    backs_off_when_refused,
    stops_retrying_when_banned,
    damaged_frames_never_reach_the_caster,
    recovers_from_a_module_power_cycle,
    stays_off_the_caster_while_the_module_is_silent,
    unconfigured_never_connects,
    waits_for_the_network,
]


def main():
    global HOST
    HOST = os.path.abspath(sys.argv[1])
    only = sys.argv[2:] or None

    def run(scenario):
        start = time.monotonic()
        try:
            scenario()
            RESULTS[scenario.__name__] = f"PASS {time.monotonic() - start:5.1f}s"
        except Exception as e:  # noqa: BLE001
            RESULTS[scenario.__name__] = f"FAIL {time.monotonic() - start:5.1f}s  {e}"

    # The network scenario uses a shared flag file, so it runs after the others
    last = [s for s in SCENARIOS if s is waits_for_the_network and (not only or s.__name__ in only)]
    rest = [threading.Thread(target=run, args=(s,)) for s in SCENARIOS if s is not waits_for_the_network and (not only or s.__name__ in only)]
    for t in rest:
        t.start()
    for t in rest:
        t.join()
    for s in last:
        run(s)

    failed = 0
    for name, result in RESULTS.items():
        print(f"{result:70.220s}  {name}")
        failed += result.startswith("FAIL")
    print(f"\n{len(RESULTS) - failed} passed, {failed} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
