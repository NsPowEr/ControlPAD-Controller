import hid
import sys
import time

VID = 0x2516
PID = 0x007B

# Captured raw wire bytes (interrupt OUT, endpoint 0x04) from Wireshark, device_address 17
def pad64(hexstr):
    b = bytes.fromhex(hexstr)
    assert len(b) <= 64
    return (b + bytes(64 - len(b))).hex()

HANDSHAKE = pad64("56810000010000000100000055555555")  # frame 223/205, sent once before color cmd
RED_CMD   = pad64("5683000001000000000100c100000000ff0000ff")
BLUE_CMD  = pad64("5683000001000000000100c1000000000000ffff")

def find_vendor_interface():
    for d in hid.enumerate(VID, PID):
        if d.get('usage_page') == 0xFF00:
            return d['path']
    return None

def send(dev, hexstr, label, prepend_zero=True):
    data = bytes.fromhex(hexstr)
    assert len(data) == 64, f"{label}: expected 64 bytes, got {len(data)}"
    buf = (bytes([0x00]) + data) if prepend_zero else data
    n = dev.write(buf)
    print(f"{label}: wrote {n} bytes (buf len {len(buf)}, prepend_zero={prepend_zero})")

def main():
    path = find_vendor_interface()
    if not path:
        print("Vendor interface (usage_page 0xFF00) not found!")
        sys.exit(1)
    print(f"Opening: {path}")
    dev = hid.device()
    dev.open_path(path)
    try:
        prepend = "--noprepend" not in sys.argv
        args = [a for a in sys.argv[1:] if a != "--noprepend"]
        color = args[0] if args else "red"
        send(dev, HANDSHAKE, "handshake", prepend_zero=prepend)
        time.sleep(0.05)
        if color == "red":
            send(dev, RED_CMD, "set_red", prepend_zero=prepend)
        elif color == "blue":
            send(dev, BLUE_CMD, "set_blue", prepend_zero=prepend)
        else:
            print("Usage: python hid_test_color.py [red|blue] [--noprepend]")
    finally:
        dev.close()

if __name__ == "__main__":
    main()
