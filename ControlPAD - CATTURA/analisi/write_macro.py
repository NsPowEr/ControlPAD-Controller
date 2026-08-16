"""Write macros by substituting them into a captured session.

Building the session by hand did not take effect, while replaying a capture
verbatim did, so this takes the app's own traffic as the skeleton and swaps
only the macro packets. Everything else — session framing, keymap, the
profile blob before the commit — stays byte-identical to a sequence that is
known to work, and the original inter-packet pacing is preserved.
"""

import pathlib
import subprocess
import sys
import time

import hid

# La codifica delle macro sta nel motore, non in una copia qui accanto.
_MOTORE = str(pathlib.Path(__file__).resolve().parent.parent.parent / "ControlPadEngine")
if _MOTORE not in sys.path:
    sys.path.append(_MOTORE)

from macro import (events_for, events_for_combo, macro_packets,     # noqa: E402
                   PRESS, LCTRL, LALT, DEL)

VID, PID, REPORT = 0x2516, 0x007B, 64
TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
# Capture 07 is the skeleton because it is a single session carrying four
# macro groups, so up to four macros can be substituted in one write.
SKELETON = "captures/07_macro_diversa.pcapng"

FLASH_SETTLE = 0.080   # the pause the app leaves after each macro body
STEP = 0.006


def device_address(pcap):
    """The pad's USB address, which changes every time it is replugged."""
    cmd = [TSHARK, "-r", pcap,
           "-Y", f"usb.idVendor == {VID} && usb.idProduct == {PID}",
           "-T", "fields", "-e", "usb.device_address"]
    raw = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    for line in raw.splitlines():
        if line.strip():
            return int(line.strip())
    raise SystemExit(f"ControlPad non trovato in {pcap}")


def out_reports(pcap):
    addr = device_address(pcap)
    cmd = [TSHARK, "-r", pcap,
           "-Y", f"usb.device_address == {addr} && usb.endpoint_address == 0x04"
                 " && usbhid.data",
           "-T", "fields", "-e", "frame.time_relative", "-e", "usbhid.data"]
    raw = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    reports, prev = [], None
    for line in raw.splitlines():
        if not line.strip():
            continue
        stamp, payload = line.split("\t")
        stamp = float(stamp)
        reports.append((bytes.fromhex(payload.strip()),
                        0.0 if prev is None else stamp - prev))
        prev = stamp
    return reports


def is_macro_packet(p):
    """A macro group is 51 18 (non-clearing) / 51 19 / 53 xx."""
    if p[0] == 0x53:
        return True
    if p[:2] == b"\x51\x19":
        return True
    return p[:2] == b"\x51\x18" and p[4:6] != b"\xff\x3f"


def remap_packet(payload, remaps):
    """Rewrite a keymap entry: 51 20 <tasto> 00 <azione a 16 bit>.

    The action is 16 bit: below 0x0100 it is a HID usage, above it a device
    function such as cycling the lighting effect. 0xFF leaves the key alone.
    """
    key = payload[2]
    if key not in remaps:
        return payload
    action = remaps[key]
    return payload[:4] + bytes([action & 0xFF, action >> 8]) + payload[6:]


def profile_packet(payload, lighting):
    """Patch the stored lighting in chunk 0 of the profile blob.

    56 83 sets the lighting that is live right now and is lost at the next
    power cycle; what survives is this blob, which the pad reloads on plug-in.
    The two carry the same fields, the profile copy shifted four bytes earlier:

        56 21 00 00 00 [effetto] 00 c1 [velocita] 00 00 00 [R G B A]

    The colour offsets come from a clean red-vs-blue diff. The effect and speed
    offsets are inferred from the layout matching 56 83, with only the static
    effect seen in a capture to confirm them.
    """
    if payload[:4] != b"\x56\x21\x00\x00":
        return payload
    effect, speed, r, g, b, a = lighting
    out = bytearray(payload)
    out[5], out[8] = effect, speed
    out[12:16] = bytes([r, g, b, a])
    return bytes(out)


def build(macros, remaps=None, lighting=None, skeleton=SKELETON):
    """macros: list of (slot, key_usage, body, name). Returns [(payload, gap)]."""
    remaps = remaps or {}
    reports = out_reports(skeleton)
    out, i, next_macro = [], 0, 0

    while i < len(reports):
        payload, gap = reports[i]
        if not is_macro_packet(payload):
            if payload[:2] == b"\x51\x20":
                payload = remap_packet(payload, remaps)
            elif lighting:
                payload = profile_packet(payload, lighting)
            out.append((payload, gap))
            i += 1
            continue

        while i < len(reports) and is_macro_packet(reports[i][0]):
            i += 1                                   # drop the original group

        if next_macro < len(macros):
            slot, key, body, name = macros[next_macro]
            next_macro += 1
            out.append((bytes([0x51, 0x18, slot, 0x00, key, PRESS]), gap))
            # 51 19 carries the macro's name as a plain ASCII string, not a
            # single byte: earlier captures only looked like one because the
            # macros were named "A" and "Z".
            out.append((bytes([0x51, 0x19, slot, 0x00]) + name.encode(), STEP))
            for p in macro_packets(body):
                out.append((p, FLASH_SETTLE))
            print(f"  slot {slot} -> tasto 0x{key:02x} '{name}': "
                  f"{len(body)//4} eventi, {len(macro_packets(body))} pacchetti")

    return out


def send_all(reports):
    path = next((d["path"] for d in hid.enumerate(VID, PID)
                 if d.get("usage_page") == 0xFF00), None)
    if path is None:
        raise SystemExit("ControlPad vendor interface not found")
    dev = hid.device()
    dev.open_path(path)
    try:
        for payload, gap in reports:
            if gap:
                time.sleep(min(gap, 0.5))
            dev.write(bytes([0x00]) + payload[:REPORT].ljust(REPORT, b"\0"))
            dev.read(REPORT, timeout_ms=100)
    finally:
        dev.close()


if __name__ == "__main__":
    KEY_3_3, KEY_3_4 = 0x16, 0x07     # (riga, colonna) sul pad
    plan = [
        (0x0c, KEY_3_4, events_for_combo([LCTRL, LALT, DEL]), "ctrlaltcanc"),
        (0x0d, KEY_3_3, events_for("CIAo FighEtta|1|1|"), "fighetta"),
    ]
    print("scrittura macro:")
    send_all(build(plan))
    print("fatto")
