"""Write raw bytes at chosen offsets into the per-key colour buffer.

Usage:  python probe_raw.py 0:ffffff  [12:ff0000 ...]

Everything not named in the arguments is left at zero, so a single triplet
placed at a known offset shows exactly which key consumes those bytes. That
pins down the stride (3 vs 4 bytes per key) and the index of the first key
without having to infer either from a pattern.
"""

import sys
import time

import hid

VID, PID = 0x2516, 0x007B
REPORT = 64

CHUNK0_HEADER = bytes.fromhex("568300000100000080010000")
CHUNK1_HEADER = bytes.fromhex("56830100")
CHUNK0_DATA = REPORT - len(CHUNK0_HEADER)   # 52
CHUNK1_DATA = REPORT - len(CHUNK1_HEADER)   # 60
BUFFER_LEN = CHUNK0_DATA + CHUNK1_DATA      # 112

HANDSHAKE = "56810000010000000100000055555555"
COMMIT = "4180"
APPLY = "51280000ff"


def pad(data):
    if isinstance(data, str):
        data = bytes.fromhex(data)
    return data + bytes(REPORT - len(data))


def send(dev, payload, label):
    dev.write(bytes([0x00]) + pad(payload))
    replies = []
    for _ in range(4):
        r = dev.read(REPORT, timeout_ms=120)
        if not r:
            break
        replies.append(bytes(r).hex()[:12])
    print(f"  {label:<10} acks={replies if replies else '<none>'}")
    time.sleep(0.005)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    buf = bytearray(BUFFER_LEN)
    for spec in sys.argv[1:]:
        off, _, hexval = spec.partition(":")
        off = int(off)
        val = bytes.fromhex(hexval)
        buf[off:off + len(val)] = val
        print(f"buffer[{off}:{off + len(val)}] = {val.hex(' ')}")

    path = next((d["path"] for d in hid.enumerate(VID, PID)
                 if d.get("usage_page") == 0xFF00), None)
    if path is None:
        raise SystemExit("ControlPad vendor interface not found")

    dev = hid.device()
    dev.open_path(path)
    try:
        send(dev, HANDSHAKE, "handshake")
        send(dev, CHUNK0_HEADER + buf[:CHUNK0_DATA], "keys.0")
        send(dev, CHUNK1_HEADER + buf[CHUNK0_DATA:], "keys.1")
        send(dev, COMMIT, "commit")
        send(dev, APPLY, "apply")
    finally:
        dev.close()


if __name__ == "__main__":
    main()
