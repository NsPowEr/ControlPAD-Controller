import re

with open("ControlPadEngine/bridge.py", "r") as f:
    content = f.read()

# 1. Add _listen_dev and _pause_polling globals
content = content.replace("POLL_INTERVAL = 1.0", "POLL_INTERVAL = 1.0\n_listen_dev = None\n_pause_polling = False")

# 2. Add _chiudi_listen_dev
chiudi_func = """
def _chiudi_listen_dev():
    global _listen_dev
    if _listen_dev is not None:
        try:
            _listen_dev.close()
        except:
            pass
        _listen_dev = None
"""
content = content.replace("def _poll_connection():", chiudi_func + "\n\ndef _poll_connection():")

# 3. Add _pause_polling to handle()
handle_start = """def handle(req):
    global _colori_fissi"""
handle_start_new = """def handle(req):
    global _colori_fissi, _pause_polling"""
content = content.replace(handle_start, handle_start_new)

handle_pause = """    if cmd not in SOLA_LETTURA + ("set_indicators",):
        _chiudi_pad_persistente()"""
handle_pause_new = """    if cmd not in SOLA_LETTURA + ("set_indicators",):
        _chiudi_pad_persistente()
    _pause_polling = True
    _chiudi_listen_dev()
    try:"""
content = content.replace(handle_pause, handle_pause_new)

# We need to indent the rest of the handle function!
# The rest of the function goes until `raise ValueError(f"comando sconosciuto: {cmd!r}")`
# Let's use regex for this
handle_body_pattern = r'(    if cmd == "ping":.*?raise ValueError\(f"comando sconosciuto: \{cmd!r\}"\))'
match = re.search(handle_body_pattern, content, re.DOTALL)
if match:
    body = match.group(1)
    indented_body = "\n".join("    " + line if line else line for line in body.split("\n"))
    indented_body += "\n    finally:\n        _pause_polling = False"
    content = content.replace(body, indented_body)

# 4. Replace _poll_connection
old_poll = """def _poll_connection():
    last = None
    while True:
        present = _device_present()
        if present != last:
            _event(event="connection", present=present)
            last = present
        time.sleep(POLL_INTERVAL)"""

new_poll = """def _poll_connection():
    global _listen_dev, _pause_polling
    last_present = None

    while True:
        try:
            present = _device_present()
            if present != last_present:
                _event(event="connection", present=present)
                last_present = present
                _chiudi_listen_dev()

            if present and not _pause_polling:
                if _listen_dev is None:
                    path = _find_path()
                    if path:
                        try:
                            d = hid.device()
                            d.open_path(path)
                            d.set_nonblocking(0)  # We will use timeout
                            _listen_dev = d
                        except Exception as e:
                            _log(f"Poll open exception: {e}")
                            _listen_dev = None

                if _listen_dev is not None:
                    try:
                        # Legge eventi asincroni generati dal pad.
                        data = _listen_dev.read(64, timeout_ms=300)
                        if data:
                            rep = bytes(data)
                            # Profilo cambiato (es: 52 00 00 00 01)
                            if len(rep) >= 5 and rep[0:4] == b"\\x52\\x00\\x00\\x00":
                                prof = rep[4]
                                if prof < 24:
                                    _log(f"   -> Rilevato cambio profilo hardware su pad: {prof}")
                                    _event(event="hardware_profile_changed", profile=prof)
                            
                            # Modalità cambiata - Effect Cycle (es: 52 28 00 00 05)
                            elif len(rep) >= 5 and rep[0:4] == b"\\x52\\x28\\x00\\x00":
                                slot = rep[4]
                                _log(f"   -> Rilevato cambio modalità hardware su pad: {slot}")
                                _event(event="hardware_mode_changed", slot=slot)
                    except Exception as e:
                        _log(f"!! errore lettura polling: {e}")
                        _chiudi_listen_dev()
            else:
                _chiudi_listen_dev()
        except Exception as e:
            _log(f"Poll loop top level exception: {e}")

        time.sleep(0.3)"""
content = content.replace(old_poll, new_poll)

with open("ControlPadEngine/bridge.py", "w") as f:
    f.write(content)
print("bridge.py patched successfully")
