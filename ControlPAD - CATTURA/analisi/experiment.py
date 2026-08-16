"""Factorial test of the two unknowns in the per-key path.

Unknowns:
  * which handshake selects per-key mode  (01/5555 static vs 02/bbbb custom)
  * whether data bytes 0..11 are a required header or just LED data

Four variants run four seconds apart, each in its own colour, so the observer
only has to report which colours appeared and in what order:

  1 RED     verbatim replay of the app's own captured frames  (control)
  2 GREEN   static handshake  + app's header bytes
  3 BLUE    custom handshake  + zeroed header
  4 YELLOW  custom handshake  + app's header bytes
"""

import time

import hid

VID, PID = 0x2516, 0x007B
REPORT = 64

CHUNK0_HEADER = bytes.fromhex("568300000100000080010000")
CHUNK1_HEADER = bytes.fromhex("56830100")
CHUNK0_DATA, CHUNK1_DATA = 52, 60
BUFFER_LEN = CHUNK0_DATA + CHUNK1_DATA

HS_STATIC = "56810000010000000100000055555555"
HS_CUSTOM = "568100000100000002000000bbbbbbbb"
COMMIT, APPLY = "4180", "51280000ff"

# First twelve data bytes exactly as the official app sent them.
APP_PREFIX = bytes.fromhex("ff0000000000ffff00000000")

# Verbatim frames captured from the app while it drove the pad (frames 881/885).
APP_CHUNK0 = bytes.fromhex(
    "568300000100000080010000ff0000000000ffff00000000ff0000ff0000ff0000"
    "ff0000ff0000ff0000ff0000ff0000ff0000ff0000ff0000ff0000ff0000ff")
APP_CHUNK1 = bytes.fromhex(
    "568301000000ff0000ff0000ff0000ff0000ff0000ff0000ff0000ff0000ff0000"
    "ff000000000000000000000000000000000000000000000000000000000000")

GRID_FIRST, GRID_LAST = 4, 28


def pad(data):
    if isinstance(data, str):
        data = bytes.fromhex(data)
    return bytes(data) + bytes(REPORT - len(data))


def send(dev, payload):
    dev.write(bytes([0x00]) + pad(payload))
    dev.read(REPORT, timeout_ms=100)
    time.sleep(0.005)


def grid_buffer(rgb, prefix):
    buf = bytearray(BUFFER_LEN)
    buf[0:len(prefix)] = prefix
    for idx in range(GRID_FIRST, GRID_LAST + 1):
        buf[idx * 3:idx * 3 + 3] = bytes(rgb)
    return buf


def run(dev, label, handshake, chunk0, chunk1):
    print(f"  -> {label}")
    send(dev, handshake)
    send(dev, chunk0)
    send(dev, chunk1)
    send(dev, COMMIT)
    send(dev, APPLY)


def main():
    path = next((d["path"] for d in hid.enumerate(VID, PID)
                 if d.get("usage_page") == 0xFF00), None)
    if path is None:
        raise SystemExit("ControlPad vendor interface not found")

    dev = hid.device()
    dev.open_path(path)
    try:
        variants = [
            ("1 ROSSO   replay verbatim dell'app", HS_STATIC, APP_CHUNK0, APP_CHUNK1),
        ]
        for label, colour, hs, prefix in [
            ("2 VERDE   handshake statico + prefisso app", (0, 255, 0), HS_STATIC, APP_PREFIX),
            ("3 BLU     handshake custom  + prefisso zero", (0, 0, 255), HS_CUSTOM, b""),
            ("4 GIALLO  handshake custom  + prefisso app", (255, 255, 0), HS_CUSTOM, APP_PREFIX),
        ]:
            buf = grid_buffer(colour, prefix)
            variants.append((label, hs,
                             CHUNK0_HEADER + buf[:CHUNK0_DATA],
                             CHUNK1_HEADER + buf[CHUNK0_DATA:]))

        for i, (label, hs, c0, c1) in enumerate(variants):
            run(dev, label, hs, c0, c1)
            if i < len(variants) - 1:
                time.sleep(4)
    finally:
        dev.close()


if __name__ == "__main__":
    main()
