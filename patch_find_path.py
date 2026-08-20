with open("ControlPadEngine/bridge.py", "r") as f:
    content = f.read()

content = content.replace("path = _find_path()", "path = next((d[\"path\"] for d in hid.enumerate(VID, PID) if d.get(\"usage_page\") == 0xFF00), None)")

with open("ControlPadEngine/bridge.py", "w") as f:
    f.write(content)
print("find_path patched")
