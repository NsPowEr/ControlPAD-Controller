"""Replay the full captured command sequence for setting a static colour.

Sequence observed in captures/03_static_red_clean.pcapng (device address 17,
interface 1, interrupt OUT endpoint 0x04):

    t=2.037  5681 ...5555 5555   handshake / begin
    t=2.044  5683 ... RR GG BB AA  write colour
    t=2.050  4180 0000...          commit
    t=2.055  5128 0000 ff          apply (ff = on, 00 = off)

Each OUT is acknowledged on endpoint 0x83 with the header echoed and the rest
zeroed, so we read after every write to confirm the channel is alive.
"""

import sys
import time

import hid

VID = 0x2516
PID = 0x007B


def pad64(hexstr):
    b = bytes.fromhex(hexstr)
    assert len(b) <= 64, f"payload too long: {len(b)}"
    return b + bytes(64 - len(b))


COLOURS = {
    "red":   "ff0000ff",
    "blue":  "0000ffff",
    "green": "00ff00ff",
}

HANDSHAKE = pad64("56810000010000000100000055555555")
COMMIT    = pad64("4180")
APPLY_ON  = pad64("51280000ff")


def colour_cmd(rgba_hex):
    return pad64("5683000001000000000100c100000000" + rgba_hex)


def find_vendor_interface():
    for d in hid.enumerate(VID, PID):
        if d.get("usage_page") == 0xFF00:
            return d["path"]
    return None


def send(dev, data, label):
    n = dev.write(bytes([0x00]) + data)
    reply = dev.read(64, timeout_ms=300)
    ack = bytes(reply).hex()[:16] if reply else "<no reply>"
    print(f"  {label:<12} wrote={n:<4} ack={ack}")
    return reply


def main():
    colour = sys.argv[1] if len(sys.argv) > 1 else "red"
    if colour not in COLOURS:
        print(f"Usage: python hid_seq.py [{'|'.join(COLOURS)}]")
        sys.exit(1)

    path = find_vendor_interface()
    if not path:
        print("Vendor interface (usage_page 0xFF00) not found")
        sys.exit(1)

    dev = hid.device()
    dev.open_path(path)
    try:
        print(f"Setting colour: {colour} ({COLOURS[colour]})")
        send(dev, HANDSHAKE, "handshake")
        time.sleep(0.005)
        send(dev, colour_cmd(COLOURS[colour]), "colour")
        time.sleep(0.005)
        send(dev, COMMIT, "commit")
        time.sleep(0.005)
        send(dev, APPLY_ON, "apply")
    finally:
        dev.close()


if __name__ == "__main__":
    main()
