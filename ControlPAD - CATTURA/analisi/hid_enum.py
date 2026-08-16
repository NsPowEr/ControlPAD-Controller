import hid

VID = 0x2516
PID = 0x007B

for d in hid.enumerate(VID, PID):
    print(f"path={d['path']}  interface={d['interface_number']}  usage_page={hex(d.get('usage_page',0))}  usage={hex(d.get('usage',0))}  product={d.get('product_string')}")
