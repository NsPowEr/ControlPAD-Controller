"""Driver for the Cooler Master ControlPad (VID 0x2516, PID 0x007B).

Protocol recovered from the USB captures in captures/:

  handshake  56 81 00 00 01 00 00 00 01 00 00 00 55 55 55 55
  colour     56 83 <chunk> 00 01 00 00 00 <mode> 01 00 <c1|00> ...
  commit     41 80
  apply      51 28 00 00 ff        (ff = apply, 00 = release)

Two colour modes share the 56 83 opcode, distinguished by byte 8:

  byte8 = 0x00, byte11 = 0xc1  -> single static colour, RGBA at offset 16
  byte8 = 0x80, byte11 = 0x00  -> per-LED table, RGB stream from offset 12,
                                  continuing into chunk 1 (4-byte header)

The static command takes RGBA (the fourth byte is brightness), but the per-LED
table is a plain stream of 3-byte RGB triplets. The grid keys start at triplet
4 and run in column-major order, top to bottom then left to right; the twelve
bytes before them are a fixed prefix.

Per-key mode needs its own handshake (02 / bb bb bb bb rather than 01 /
55 55 55 55). With the static handshake, or without the prefix, only the keys
carried by the first chunk light up.

Every OUT report is acknowledged on the IN endpoint with its header echoed.
The device also emits unsolicited ff aa .. reports, so reads may need draining
before the matching acknowledgement appears.
"""

import time

import hid

VID = 0x2516
PID = 0x007B
REPORT_SIZE = 64

INDICATOR_LEDS = 4      # the four LEDs above the pad occupy the first triplets
GRID_ROWS = 5
GRID_COLS = 5
NUM_LEDS = INDICATOR_LEDS + GRID_ROWS * GRID_COLS

CHUNK0_HEADER = bytes.fromhex("568300000100000080010000")
CHUNK1_HEADER = bytes.fromhex("56830100")
CHUNK0_DATA = REPORT_SIZE - len(CHUNK0_HEADER)   # 52
CHUNK1_DATA = REPORT_SIZE - len(CHUNK1_HEADER)   # 60
BUFFER_LEN = CHUNK0_DATA + CHUNK1_DATA           # 112

HANDSHAKE_STATIC = "56810000010000000100000055555555"
HANDSHAKE_PERKEY = "568100000100000002000000bbbbbbbb"
STATIC_HEADER = "5683000001000000000100c100000000"
COMMIT = "4180"
APPLY = "51280000ff"

# The twelve bytes ahead of the grid, copied from the official app. Zeroing
# them costs the keys carried by the second chunk.
DATA_PREFIX = bytes.fromhex("ff0000000000ffff00000000")

OFF = (0, 0, 0)

# Effect ids read off the 56 83 command, with the speed the app paired with
# each. Only the static one is named with certainty; the rest were captured by
# cycling through the app's list, so the labels are still to be confirmed.
EFFECT_STATIC = 0x01
EFFECTS = [(0x01, 0x00), (0x30, 0x0C), (0x31, 0x08),
           (0x32, 0x07), (0x34, 0x04), (0x83, 0x04)]


def led_index(col, row):
    """LED index for a grid position, both 0-based, origin top-left."""
    return INDICATOR_LEDS + col * GRID_ROWS + row


def _pad(data):
    if isinstance(data, str):
        data = bytes.fromhex(data)
    assert len(data) <= REPORT_SIZE, f"payload too long: {len(data)}"
    return data + bytes(REPORT_SIZE - len(data))


class ControlPad:
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.dev = None

    def __enter__(self):
        path = next((d["path"] for d in hid.enumerate(VID, PID)
                     if d.get("usage_page") == 0xFF00), None)
        if path is None:
            raise RuntimeError("ControlPad vendor interface not found")
        self.dev = hid.device()
        self.dev.open_path(path)
        return self

    def __exit__(self, *exc):
        if self.dev:
            self.dev.close()

    def _send(self, payload, label=""):
        # One read, short timeout: the chunked colour transaction is timing
        # sensitive and stalls if consecutive reports are spaced too far apart.
        self.dev.write(bytes([0x00]) + _pad(payload))
        reply = self.dev.read(REPORT_SIZE, timeout_ms=100)
        if self.verbose:
            print(f"  {label:<10} {bytes(reply).hex()[:8] if reply else '<none>'}")
        time.sleep(0.005)

    def _finish(self):
        self._send(COMMIT, "commit")
        self._send(APPLY, "apply")

    def set_effect(self, effect, r=0xFF, g=0xFF, b=0xFF, speed=0x00,
                   brightness=0xFF):
        """Select a firmware effect. effect 0x01 is the plain static colour.

        Effects animate on the device: the app sends one report per change and
        never streams frames, so nothing has to stay running on the host.
        """
        header = bytes([0x56, 0x83, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00,
                        0x00, effect, 0x00, 0xC1, speed, 0x00, 0x00, 0x00])
        self._send(HANDSHAKE_STATIC, "handshake")
        self._send(header + bytes([r, g, b, brightness]), "effect")
        self._finish()

    def set_static(self, r, g, b, brightness=0xFF):
        """Light the whole pad in one colour."""
        self.set_effect(EFFECT_STATIC, r, g, b, brightness=brightness)

    def set_indicators(self, colours):
        """Colour the four LEDs above the pad. colours: list of (r, g, b).

        These are the profile indicators and are not part of the per-key
        table — writing that one black leaves them untouched. They have a
        command of their own, and it takes effect immediately rather than
        going through the profile, so they can be animated.
        """
        data = bytearray()
        for i in range(4):
            data += bytes(colours[i] if i < len(colours) else (0, 0, 0))
        self._send("4104", "begin")
        self._send(bytes.fromhex("5550fc000c") + data, "indicators")
        self._send(COMMIT, "commit")

    def set_leds(self, colours):
        """colours: {led_index: (r, g, b)}. Unlisted LEDs go dark."""
        buf = bytearray(BUFFER_LEN)
        buf[0:len(DATA_PREFIX)] = DATA_PREFIX
        for idx, (r, g, b) in colours.items():
            buf[idx * 3:idx * 3 + 3] = bytes([r, g, b])

        self._send(HANDSHAKE_PERKEY, "handshake")
        self._send(CHUNK0_HEADER + buf[:CHUNK0_DATA], "keys.0")
        self._send(CHUNK1_HEADER + buf[CHUNK0_DATA:], "keys.1")
        self._finish()

    def set_grid(self, grid):
        """grid: {(col, row): (r, g, b)}, both 0-based from the top-left."""
        self.set_leds({led_index(c, r): rgb for (c, r), rgb in grid.items()})


if __name__ == "__main__":
    import sys

    STRIPES = [(255, 0, 0), (0, 255, 0), (0, 0, 255),
               (255, 255, 0), (255, 0, 255)]
    NAMES = ["ROSSO", "VERDE", "BLU", "GIALLO", "MAGENTA"]

    mode = sys.argv[1] if len(sys.argv) > 1 else "stripes"
    with ControlPad(verbose=True) as pad:
        if mode == "stripes":
            # One colour per column: proves stride, ordering and offset at once.
            for col, name in enumerate(NAMES):
                print(f"  colonna {col + 1} -> {name}")
            pad.set_grid({(c, r): STRIPES[c]
                          for c in range(GRID_COLS) for r in range(GRID_ROWS)})
        elif mode == "static":
            pad.set_static(255, 0, 0)
        else:
            print("Usage: python controlpad.py [stripes|static]")
