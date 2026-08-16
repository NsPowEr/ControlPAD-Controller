"""Replay every OUT report of a capture, byte for byte, in the original order.

This is the control experiment for config writes: if replaying the app's own
traffic reproduces the state that capture left behind, the transport is sound
and any failure lies in a hand-built sequence. If even this does nothing, the
problem is in how reports are sent rather than in their contents.
"""

import subprocess
import sys
import time

import hid

VID, PID, REPORT = 0x2516, 0x007B, 64
TSHARK = r"C:\Program Files\Wireshark\tshark.exe"


def out_reports(pcap):
    """Return (payload, gap_before) pairs, keeping the app's original pacing.

    The gaps matter: the app waits about 70 ms after each macro body (53 00),
    which is the device committing to flash. Sending the next report too early
    loses the write, while the lighting path has no such pause and survives
    replay at full speed.
    """
    cmd = [TSHARK, "-r", pcap,
           "-Y", "usb.device_address == 17 && usb.endpoint_address == 0x04 && usbhid.data",
           "-T", "fields", "-e", "frame.time_relative", "-e", "usbhid.data"]
    raw = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout

    reports, prev = [], None
    for line in raw.splitlines():
        if not line.strip():
            continue
        stamp, payload = line.split("\t")
        stamp = float(stamp)
        gap = 0.0 if prev is None else stamp - prev
        reports.append((bytes.fromhex(payload.strip()), gap))
        prev = stamp
    return reports


def main():
    pcap = sys.argv[1]
    reports = out_reports(pcap)
    print(f"{len(reports)} report da riprodurre")

    path = next((d["path"] for d in hid.enumerate(VID, PID)
                 if d.get("usage_page") == 0xFF00), None)
    if path is None:
        raise SystemExit("ControlPad vendor interface not found")

    dev = hid.device()
    dev.open_path(path)
    try:
        for payload, gap in reports:
            if gap:
                time.sleep(gap)
            dev.write(bytes([0x00]) + payload[:REPORT].ljust(REPORT, b"\0"))
            dev.read(REPORT, timeout_ms=100)
        print(f"inviati {len(reports)} report")
    finally:
        dev.close()


if __name__ == "__main__":
    main()
