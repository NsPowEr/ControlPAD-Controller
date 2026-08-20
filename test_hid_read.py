import hid
for d in hid.enumerate(0x2516, 0x007b):
    if d.get("usage_page") == 0xFF00:
        dev = hid.device()
        dev.open_path(d["path"])
        dev.set_nonblocking(1)
        data = dev.read(64)
        print("Read data:", data)
        dev.close()
