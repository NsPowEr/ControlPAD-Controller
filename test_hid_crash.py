import hid
import threading
import time

path = next(d["path"] for d in hid.enumerate() if d.get("usage_page") == 0xFF00)
dev = hid.device()
dev.open_path(path)
dev.set_nonblocking(0)

def reader():
    try:
        print("Reader waiting...")
        data = dev.read(64, timeout_ms=5000)
        print("Read done:", data)
    except Exception as e:
        print("Read exception:", e)

t = threading.Thread(target=reader)
t.start()
time.sleep(1)
print("Closing device...")
dev.close()
print("Device closed.")
t.join()
