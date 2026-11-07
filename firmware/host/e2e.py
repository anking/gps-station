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
from f9p_sim import F9pSim, crc24q  # noqa: E402

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


class Base:
    def __init__(self, sim, caster, *args):
        self.lines = []
        self.errors = []
        self.process = subprocess.Popen(
            [HOST, "--serial", sim.path, "--host", "127.0.0.1", "--port", str(caster.port), "--mount", "TEST", "--password", "secret", *args],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
        threading.Thread(target=self._read_status, daemon=True).start()
        threading.Thread(target=self._read_errors, daemon=True).start()

    def _read_status(self):
        for line in self.process.stdout:
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
        wait_for(lambda: base.status.get("have_position"), 5, "position")
        check(abs(base.status["lat"] - 40.1234567) < 1e-6, f"latitude {base.status}")
        check(base.status["height_m"] == 300.0, f"height in meters {base.status}")
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
        check(len(sim.commands) == 0, "must not touch the module")
    finally:
        process.kill(), process.wait(), sim.close(), caster.close()


SCENARIOS = [
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
