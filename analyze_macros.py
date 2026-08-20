import sys, dpkt, binascii

def analyze(pcapng_file):
    with open(pcapng_file, 'rb') as f:
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
                # Print macro packets
                if payload[0] == 0x51 and payload[1] == 0x19:
                    name = payload[4:16].decode('utf-8', 'ignore').strip('\x00')
                    print(f"Macro Name: {name}")
                if payload[0] == 0x53:
                    print(f"Macro Data: {binascii.hexlify(payload[:32]).decode('utf-8')}")
                    
if __name__ == '__main__':
    analyze(sys.argv[1])
