import os, sys, dpkt, binascii, glob

def analyze(directory):
    actions = set()
    for pcapng_file in glob.glob(os.path.join(directory, "*.pcapng")):
        with open(pcapng_file, 'rb') as f:
            try:
                reader = dpkt.pcapng.Reader(f)
                for ts, buf in reader:
                    if len(buf) < 27: continue
                    header_len = int.from_bytes(buf[0:2], 'little')
                    if header_len + 64 > len(buf): continue
                    
                    info = buf[16]
                    data_length = int.from_bytes(buf[23:27], 'little')
                    direction = info & 0x01
                    
                    if direction == 0 and data_length == 64:
                        payload = buf[header_len:header_len+data_length]
                        if payload[0] == 0x51 and payload[1] == 0x20:
                            action_hex = binascii.hexlify(payload[4:8]).decode('utf-8')
                            if action_hex != "ff000000":
                                actions.add(action_hex)
            except Exception as e:
                pass
    print("All unique actions:", sorted(list(actions)))
                    
if __name__ == '__main__':
    analyze(sys.argv[1])
