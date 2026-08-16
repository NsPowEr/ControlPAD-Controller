"""Lettore pcapng/USBPcap in Python puro — niente tshark, niente Windows.

Gli script più vecchi in questa cartella invocavano tshark.exe con un path
Windows: inutilizzabili su macOS, dove il progetto è finito. Le catture però
restano l'unica fonte di verità per le parti di protocollo non ancora
decodificate, quindi serviva un modo di rileggerle qui.

Formato, dalle specifiche pcapng:

    blocco := tipo(4) lunghezza_totale(4) corpo lunghezza_totale(4)

Interessa solo l'Enhanced Packet Block (tipo 0x06), il cui corpo è:

    interface_id(4) ts_high(4) ts_low(4) captured_len(4) original_len(4) dati…

I dati sono un pacchetto USBPcap, che comincia col proprio header:

    headerLen(2) irpId(8) status(4) function(2) info(1) bus(2)
    device(2) endpoint(1) transfer(1) dataLength(4)

Il payload vero (il report da 64 byte) comincia a `headerLen`. Il bit alto di
`endpoint` è la direzione: 1 = IN (risposte del device), 0 = OUT (comandi
dell'app). Per capire cosa fa il software ufficiale servono gli OUT.
"""

import struct
import sys

EPB = 0x00000006
SHB = 0x0A0D0D0A


def _blocks(data):
    """Scorre i blocchi del file, gestendo entrambi gli endian."""
    endian = "<"
    offset = 0
    while offset + 12 <= len(data):
        block_type = struct.unpack_from(endian + "I", data, offset)[0]

        # La Section Header Block porta un magic che rivela l'endianness.
        if block_type == SHB:
            magic = struct.unpack_from("<I", data, offset + 8)[0]
            endian = "<" if magic == 0x1A2B3C4D else ">"
            block_type = struct.unpack_from(endian + "I", data, offset)[0]

        length = struct.unpack_from(endian + "I", data, offset + 4)[0]
        if length < 12 or offset + length > len(data):
            break
        yield block_type, data[offset + 8:offset + length - 4], endian
        offset += length


def packets(path):
    """(timestamp_secondi, endpoint, payload) per ogni pacchetto USB."""
    with open(path, "rb") as f:
        data = f.read()

    for block_type, body, endian in _blocks(data):
        if block_type != EPB:
            continue

        _, ts_hi, ts_lo, captured, _ = struct.unpack_from(endian + "IIIII", body, 0)
        raw = body[20:20 + captured]
        if len(raw) < 27:
            continue

        header_len = struct.unpack_from("<H", raw, 0)[0]
        endpoint = raw[21]
        payload = raw[header_len:]

        # Il timestamp è in microsecondi su 64 bit, salvo risoluzioni esotiche
        # che queste catture non usano.
        ts = ((ts_hi << 32) | ts_lo) / 1_000_000
        yield ts, endpoint, payload


def out_reports(path, endpoint=0x04, size=64):
    """(secondi_dal_precedente, payload) dei soli report OUT non vuoti.

    Il ritardo fra un report e il successivo è parte del protocollo quanto i
    byte: dopo ogni corpo macro l'app aspetta ~72 ms perché il device scrive
    in flash, e senza quella pausa il comando viene accettato senza effetto.
    """
    previous = None
    for ts, ep, payload in packets(path):
        if ep != endpoint or len(payload) < size:
            continue
        gap = 0.0 if previous is None else ts - previous
        previous = ts
        yield gap, payload[:size]


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(1)

    for gap, payload in out_reports(sys.argv[1]):
        print(f"{gap * 1000:8.1f} ms  {payload.hex()}")
