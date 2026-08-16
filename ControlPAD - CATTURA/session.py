"""Scrittura della configurazione permanente: macro, rimappature, funzioni.

Costruire la sessione da zero non funziona nemmeno con tutti i byte corretti —
il dispositivo la ignora in silenzio. Quello che funziona e partire dalla
sessione registrata dall'app (skeleton.py) e sostituirne le sole parti che
interessano, lasciando intatto tutto il resto: inquadramento, tabelle di
servizio e blob di profilo finale.

Questo modulo non richiede ne tshark ne i file di cattura.
"""

import time

import hid

from layout import tasto_da_indice_colonne
from macro import macro_packets, PRESS
from skeleton import SESSIONE

VID, PID, REPORT = 0x2516, 0x007B, 64

FLASH_SETTLE = 0.080   # pausa dopo ogni corpo macro: scrittura in flash
STEP = 0.006

NESSUNA_RIMAPPATURA = 0x00FF

# Funzioni assegnabili a un tasto o a una rotella, dalla cattura 11.
FUNZIONI = {
    "play_pausa":      0x00F0,
    "stop":            0x00F1,
    "traccia_prec":    0x00F2,
    "traccia_succ":    0x00F3,
    "muto":            0x00F4,
    "volume_giu":      0x00F5,
    "volume_su":       0x00F6,
    "effetto_avanti":  0x0181,
    "effetto_indietro": 0x0182,
    "velocita_giu":    0x0190,
    "velocita_su":     0x0191,
    "luce_su":         0x0192,
    "luce_giu":        0x0193,
    "seleziona_profilo": 0x0110,
}


def _macro_packet(p):
    """Un gruppo macro e 51 18 (non di azzeramento), 51 19 oppure 53 xx."""
    if p[0] == 0x53 or p[:2] == b"\x51\x19":
        return True
    return p[:2] == b"\x51\x18" and p[4:6] != b"\xff\x3f"


def _con_rimappatura(payload, remaps):
    """51 20 <tasto> 00 <azione a 16 bit>: sotto 0x0100 e un codice HID."""
    key = payload[2]
    if key not in remaps:
        return payload
    azione = remaps[key]
    return payload[:4] + bytes([azione & 0xFF, azione >> 8]) + payload[6:]


def _con_illuminazione(payload, lighting):
    """Illuminazione memorizzata nel chunk 0 del blob di profilo.

    Riguarda solo lo slot 0 (Statico) dei 14 disponibili: se il pad ne sta
    mostrando un altro, la modifica non si vede. Serve per l'accensione, non
    per cambiare quello che e a schermo — per quello c'e ControlPad.set_effect.
    """
    if payload[:4] != b"\x56\x21\x00\x00":
        return payload
    effetto, velocita, r, g, b, a = lighting
    out = bytearray(payload)
    out[5], out[8] = effetto, velocita
    out[12:16] = bytes([r, g, b, a])
    return bytes(out)


def _tabella_profili(profile_keys):
    """51 90: quale profilo attiva ciascun tasto, indicizzato per colonne.

    Il valore predefinito e l'identita, che equivale a nessuna assegnazione.
    """
    tabella = bytearray(range(24))
    for indice_led, profilo in profile_keys.items():
        tabella[indice_led] = profilo
    return bytes.fromhex("51900000") + tabella


def costruisci(macros=(), remaps=None, lighting=None, profile_keys=None):
    """Prepara la sessione da inviare.

    macros       sequenza di (slot, codice_tasto, eventi, nome)
    remaps       {codice_tasto: azione}, azione da FUNZIONI o codice HID
    lighting     (effetto, velocita, r, g, b, a) da salvare nel profilo
    profile_keys {indice_tasto_per_colonne: numero_profilo}
    """
    remaps = dict(remaps or {})

    # Un tasto selettore vuole due scritture: l'azione nella keymap, che lo
    # marca come tale, e la voce nella tabella, che dice quale profilo. Con la
    # sola tabella il tasto conserva l'azione precedente e non cambia nulla.
    for indice in (profile_keys or {}):
        remaps[tasto_da_indice_colonne(indice)] = FUNZIONI["seleziona_profilo"]

    fuori = []
    macro_emesse = False

    for hexstr, gap in SESSIONE:
        payload = bytes.fromhex(hexstr)

        if _macro_packet(payload):
            if macro_emesse:
                continue                      # scarta i gruppi originali
            macro_emesse = True
            for slot, tasto, eventi, nome in macros:
                fuori.append((bytes([0x51, 0x18, slot, 0x00, tasto, PRESS]), gap))
                fuori.append((bytes([0x51, 0x19, slot, 0x00]) + nome.encode(), STEP))
                for p in macro_packets(eventi):
                    fuori.append((p, FLASH_SETTLE))
            continue

        if profile_keys and payload[:2] == b"\x51\x94" and payload[2] == 0:
            fuori.append((bytes.fromhex("52900000"), STEP))
            fuori.append((_tabella_profili(profile_keys), STEP))
            profile_keys = None               # una volta sola

        if payload[:2] == b"\x51\x20":
            payload = _con_rimappatura(payload, remaps)
        elif lighting:
            payload = _con_illuminazione(payload, lighting)

        fuori.append((payload, gap))

    return fuori


def invia(reports, verbose=False):
    path = next((d["path"] for d in hid.enumerate(VID, PID)
                 if d.get("usage_page") == 0xFF00), None)
    if path is None:
        raise SystemExit("ControlPad non trovato: e collegato?")
    dev = hid.device()
    dev.open_path(path)
    try:
        for payload, gap in reports:
            if gap:
                time.sleep(min(gap, 0.5))
            dev.write(bytes([0x00]) + payload[:REPORT].ljust(REPORT, b"\0"))
            dev.read(REPORT, timeout_ms=100)
    finally:
        dev.close()
    if verbose:
        print(f"inviati {len(reports)} report")


def scrivi(macros=(), remaps=None, lighting=None, profile_keys=None,
           verbose=False):
    """Scorciatoia: costruisce e invia in un colpo solo."""
    invia(costruisci(macros, remaps, lighting, profile_keys), verbose)
