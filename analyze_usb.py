import sys
import dpkt
import binascii

def analyze(pcapng_file):
    with open(pcapng_file, 'rb') as f:
        reader = dpkt.pcapng.Reader(f)
        packet_idx = 0
        for ts, buf in reader:
            packet_idx += 1
            # USBPcap header is 27 bytes long.
            # struct _USBPcapURB {
            #     UINT16 headerLen; (2)
            #     UINT64 irpId; (8)
            #     UINT32 status; (4)
            #     UINT16 function; (2)
            #     UINT8 info; (1)
            #     UINT16 bus; (2)
            #     UINT16 device; (2)
            #     UINT8 endpoint; (1)
            #     UINT8 transfer; (1)
            #     UINT32 dataLength; (4)
            # }
            if len(buf) < 27:
                continue
                
            header_len = int.from_bytes(buf[0:2], 'little')
            
            # URB_BULK / URB_INTERRUPT typically have transfer_type=1 (Isochronous=0, Interrupt=1, Control=2, Bulk=3)
            # and info bit 0 indicates direction (0=OUT/host-to-device, 1=IN/device-to-host)
            info = buf[16]
            endpoint = buf[21]
            transfer_type = buf[22]
            data_length = int.from_bytes(buf[23:27], 'little')
            
            # We are interested in OUT Interrupt transfers (or just any OUT transfer with payload)
            direction = info & 0x01
            
            if direction == 0 and len(buf) >= header_len + data_length and data_length == 64:
                payload = buf[header_len:header_len+data_length]
                # Filter for typical CoolerMaster command prefixes
                if payload[0] in (0x51, 0x53):
                    print(f"Packet {packet_idx}: {binascii.hexlify(payload[:32]).decode('utf-8')}...")
                    
if __name__ == '__main__':
    analyze(sys.argv[1])
