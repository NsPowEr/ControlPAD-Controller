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

import effects
from controlpad import attendi_ack
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


# Le quattro voci di rotella nella keymap sono gia assegnate di fabbrica, e in
# tutte le catture allo stesso modo: per una rotella "nessuna assegnazione" non
# vuol dire 0x00FF, vuol dire questo.
ROTELLE_DI_FABBRICA = {
    0xC6: 0x0192,   # rotella sinistra, verso -: LED piu luminoso
    0xC7: 0x0193,   # rotella sinistra, verso +: LED piu scuro
    0xF5: 0x00F5,   # rotella destra, verso -: volume giu
    0xF6: 0x00F6,   # rotella destra, verso +: volume su
}


def _con_rimappatura(payload, remaps):
    """51 20 <tasto> 00 <azione a 16 bit>: sotto 0x0100 e un codice HID.

    Un tasto assente da `remaps` **non** conserva il valore della sessione
    registrata. Quella e la configurazione di chi ha fatto la cattura, e
    lasciarla passare significava scrivere sul pad dieci rimappature che
    nessuno aveva chiesto — `2` che batte `3`, `r` che batte `t`, `f` che manda
    Invio, e `x` `c` `v` `Alt` muti perche nella cattura ci stavano sopra le
    macro. L'interfaccia mostrava "default" e il pad faceva altro.

    Chi non e in `remaps` torna quindi a 0x00FF, il comportamento di fabbrica.
    Le rotelle fanno eccezione, vedi ROTELLE_DI_FABBRICA.
    """
    key = payload[2]
    azione = remaps.get(key, ROTELLE_DI_FABBRICA.get(key, NESSUNA_RIMAPPATURA))
    return payload[:4] + bytes([azione & 0xFF, azione >> 8]) + payload[6:]


CHUNK_DATI = 60          # byte utili di un report 56 21, dopo l'header di 4


def _blob_illuminazione(sessione):
    """Ricostruisce il blob di illuminazione dai report della sessione.

    L'illuminazione salvata nel pad sta in due tabelle che viaggiano insieme:

    * `56 15 <slot> 00 | <tipo> 00 <fine> 00 | <marcatore>` — quattordici voci,
      una per modalita, dove `fine` e la fine del record di quello slot in
      parole da 4 byte;
    * `56 21 <chunk> 00 | <60 byte>` — undici report che, messi in fila,
      formano un unico flusso di 660 byte con dentro i record veri.

    Un record puo quindi stare a cavallo di due report: va ricomposto il flusso
    intero, modificato, e poi rispezzettato.
    """
    tabella, chunk = [], {}
    for hexstr, _ in sessione:
        p = bytes.fromhex(hexstr)
        if p[:2] == b"\x56\x15":
            tabella.append((p[2], p[4], p[6]))        # slot, tipo, fine
        elif p[:2] == b"\x56\x21":
            chunk[p[2]] = p[4:4 + CHUNK_DATI]
    tabella.sort()
    flusso = b"".join(chunk[i] for i in sorted(chunk))
    return tabella, bytearray(flusso)


def _confini(tabella):
    """(inizio, fine) del record di ogni slot dentro il flusso."""
    fini = [fine * 4 for _, _, fine in tabella]
    return list(zip([0] + fini[:-1], fini))


def _marcatore(record):
    """Posizione di `00 <id> 00 c1` nel record: e da li che si contano i campi.

    Cercarlo invece di fidarsi di un offset fisso rende il tutto indipendente
    dai byte di intestazione, che cambiano da record a record e non sono
    ancora decodificati.
    """
    for i in range(len(record) - 3):
        if record[i] == 0x00 and record[i + 2] == 0x00 and record[i + 3] == 0xC1:
            return i
    return None


def _scrivi_record(flusso, inizio, fine, tipo, color1, color2, velocita):
    """Colore e velocita dentro il record di uno slot.

    Le posizioni sono le stesse del comando dal vivo, contate dal marcatore:
    tipo 1 (un colore) velocita a +4 e RGBA a +8; tipo 2 (i sei effetti
    reattivi) colore di fondo a +8, velocita a +20, colore di reazione a +24.
    """
    record = flusso[inizio:fine]
    m = _marcatore(record)
    if m is None:
        return

    def metti(offset, valore):
        if valore is None:
            return
        posizione = inizio + m + offset
        if posizione + len(valore) <= fine:
            flusso[posizione:posizione + len(valore)] = bytes(valore)

    if tipo == 1:
        metti(4, [velocita] if velocita is not None else None)
        metti(8, color1)
    else:
        metti(8, color1)
        metti(20, [velocita] if velocita is not None else None)
        metti(24, color2)


def _scrivi_perkey(flusso, inizio, fine, tasti):
    """La tabella per-tasto ("Personalizza") dentro il blob di profilo.

    E lo slot che fa ricomparire la vecchia configurazione a colori sparsi: i
    suoi byte sono i colori per singolo tasto salvati dal software ufficiale, e
    finche non li si riscrive il pad li ripesca dalla flash a ogni ricarica.

    Il punto dove cominciano si trova dall'intestazione del comando dal vivo,
    `80 01 00 00`, che il record si porta dietro; subito dopo vengono i dodici
    byte che precedono la griglia e poi le venticinque terzine, in ordine per
    colonne come i LED.
    """
    record = flusso[inizio:fine]
    testa = record.find(bytes.fromhex("80010000"))
    if testa < 0 or not tasti:
        return
    dati = inizio + testa + 4 + 12             # +12: il prefisso prima della griglia
    for i, rgb in enumerate(tasti[:25]):
        posizione = dati + i * 3
        if posizione + 3 <= fine:
            flusso[posizione:posizione + 3] = bytes(rgb)


def _con_illuminazione(sessione, lighting):
    """Il flusso del blob con dentro i colori scelti dall'utente.

    Va scritto, non saltato: quello che il pad conserva in flash e cio con cui
    si riaccende e cio che ripesca quando ricarica la mappatura. Lasciandolo
    intatto tornava la configurazione dell'ultima sessione del software
    ufficiale, che e esattamente il difetto segnalato.

    Si scrivono **tutti** gli slot, Personalizza compreso: quello non e un
    effetto ma la tabella dei colori per singolo tasto, ed e proprio lo slot
    che faceva ricomparire la configurazione a colori sparsi del software
    ufficiale — escluderlo perche "non e un effetto" era il difetto. Cosi
    qualunque modalita il pad stia mostrando, o l'utente scelga col tasto
    "effetto successivo", i colori sono i suoi.
    """
    tabella, flusso = _blob_illuminazione(sessione)
    if not tabella:
        return None

    color1 = lighting.get("color1")
    color2 = lighting.get("color2") or color1
    velocita = lighting.get("speed")

    for (slot, tipo, _), (inizio, fine) in zip(tabella, _confini(tabella)):
        if slot < len(effects.SLOT_ORDER) and effects.SLOT_ORDER[slot] == "custom":
            _scrivi_perkey(flusso, inizio, fine, lighting.get("perkey"))
        else:
            _scrivi_record(flusso, inizio, fine, tipo, color1, color2, velocita)

    return bytes(flusso)


# Lo stato di illuminazione persistente e la selezione della modalita: sono i
# due punti che decidono con cosa il pad si riaccende, e la sessione registrata
# li porta coi valori della cattura.
STATO_ILLUMINAZIONE = "5550280005"      # + 17 <slot> <velocita> ff ff
SELEZIONE_MODALITA = "51280000"         # + <slot>;  ff = riapplica


def _stato_illuminazione(slot, velocita):
    """`55 50 28 00 05 17 <slot> <velocita> ff ff`, cioe cosa mostrare all'avvio.

    Nelle catture dell'app questo registro vale `17 ff ff ff ff` quasi sempre e
    `17 09 04 ff ff` nella cattura 11, dove l'utente aveva girato effetto e
    velocita coi tasti: slot 9, velocita 4. Rileggendolo dal dispositivo si
    ritrova quello che vi si e scritto per ultimo, scollegamenti compresi.

    Ricopiarlo dalla cattura significava scrivere "nessuna selezione" a ogni
    sessione, e il pad all'accensione ripiegava sul suo default invece di
    mostrare la modalita scelta.
    """
    return bytes.fromhex(STATO_ILLUMINAZIONE) + bytes(
        [0x17, slot & 0xFF, velocita & 0xFF, 0xFF, 0xFF])


def _slot_modalita(lighting):
    """(slot, velocita) della modalita scelta, o (None, None) se non e detta.

    Lo slot e l'indice nella tabella delle quattordici modalita, la stessa che
    `56 15` enumera e che `51 28 00 00 <slot>` seleziona.
    """
    modalita = (lighting or {}).get("mode")
    if modalita not in effects.SLOT_ORDER:
        return None, None
    velocita = lighting.get("speed") or 0
    return effects.SLOT_ORDER.index(modalita), int(velocita)


def _tabella_profili(profile_keys):
    """51 90: quale profilo attiva ciascun tasto, indicizzato per colonne.

    Il valore predefinito e l'identita, che equivale a nessuna assegnazione.
    """
    tabella = bytearray(range(24))
    for indice_led, profilo in profile_keys.items():
        tabella[indice_led] = profilo
    return bytes.fromhex("51900000") + tabella


def _gruppo_indicatori(colori):
    """I quattro LED sopra il pad, nella forma e nel punto della cattura.

    Da solo il comando non si vede: `captures/12_colori profilo.pcapng` mostra
    che il software ufficiale lo manda **dentro** la scrittura di sessione,
    subito dopo la coppia `52 94`, e mai isolato. I colori sono per profilo,
    quindi seguono la sessione del profilo a cui appartengono.

        41 04
        55 50 fc 00 0c <R G B> × 4
        41 80
    """
    dati = bytearray()
    for i in range(4):
        dati += bytes(colori[i] if i < len(colori) else (0, 0, 0))
    return [
        (bytes.fromhex("4180"), STEP),
        (bytes.fromhex("4104"), STEP),
        (bytes.fromhex("5550fc000c") + bytes(dati), STEP),
    ]


def costruisci(macros=(), remaps=None, lighting=None, profile_keys=None,
               indicators=None):
    """Prepara la sessione da inviare.

    macros       sequenza di (slot, codice_tasto, eventi, nome)
    remaps       {codice_tasto: azione}, azione da FUNZIONI o codice HID
    lighting     {"color1": [r,g,b,a], "color2": [...], "speed": n,
                 "perkey": [(r,g,b)] * 25, "mode": chiave di effects.SLOT_ORDER}
                 da scrivere in tutti gli slot del blob di profilo; "mode" dice
                 anche quale slot il pad deve mostrare all'accensione
    profile_keys {indice_tasto_per_colonne: numero_profilo}
    indicators   [(r, g, b)] × 4 per i LED sopra il pad
    """
    remaps = dict(remaps or {})

    # Un tasto con una macro non deve battere anche il suo carattere: nelle
    # catture l'app ufficiale gli scrive azione 0x0000 nella keymap, ed e
    # esattamente sui quattro tasti che li portavano una macro.
    for _, tasto, _, _ in macros:
        remaps.setdefault(tasto, 0x0000)

    # Un tasto selettore vuole due scritture: l'azione nella keymap, che lo
    # marca come tale, e la voce nella tabella, che dice quale profilo. Con la
    # sola tabella il tasto conserva l'azione precedente e non cambia nulla.
    for indice in (profile_keys or {}):
        remaps[tasto_da_indice_colonne(indice)] = FUNZIONI["seleziona_profilo"]

    fuori = []
    macro_emesse = False
    flusso = _con_illuminazione(SESSIONE, lighting) if lighting else None
    # `slot_luce`, non `slot`: il ciclo delle macro piu sotto scorre anche lui
    # su una variabile che si chiamerebbe cosi, e sovrascrivendola mandava al
    # pad il numero di slot dell'ultima macro al posto della modalita scelta —
    # con una macro nello slot 8 il pad si riaccendeva su Lampeggio.
    slot_luce, velocita_slot = _slot_modalita(lighting)

    for hexstr, gap in SESSIONE:
        payload = bytes.fromhex(hexstr)

        if slot_luce is not None:
            # I due punti che decidono l'accensione. Senza toccarli, la sessione
            # scriveva i colori giusti in tutti gli slot e poi diceva al pad di
            # mostrare lo slot della cattura, con lo stato persistente a
            # "nessuna selezione".
            if payload[:5] == bytes.fromhex(STATO_ILLUMINAZIONE):
                payload = _stato_illuminazione(slot_luce, velocita_slot)
            elif payload[:4] == bytes.fromhex(SELEZIONE_MODALITA) and payload[4] != 0xFF:
                payload = bytes.fromhex(SELEZIONE_MODALITA) + bytes([slot_luce])

        if flusso is not None and payload[:2] == b"\x56\x21":
            # Stesso report, stessa posizione nella sequenza: cambia solo il
            # contenuto, preso dal flusso riscritto coi colori dell'utente.
            inizio = payload[2] * CHUNK_DATI
            payload = payload[:4] + flusso[inizio:inizio + CHUNK_DATI]
            fuori.append((payload, gap))
            continue

        if _macro_packet(payload):
            if macro_emesse:
                continue                      # scarta i gruppi originali
            macro_emesse = True
            for slot_macro, tasto, eventi, nome in macros:
                fuori.append((bytes([0x51, 0x18, slot_macro, 0x00, tasto, PRESS]), gap))
                fuori.append((bytes([0x51, 0x19, slot_macro, 0x00]) + nome.encode(), STEP))
                for p in macro_packets(eventi):
                    fuori.append((p, FLASH_SETTLE))
            continue

        if profile_keys and payload[:2] == b"\x51\x94" and payload[2] == 0:
            fuori.append((bytes.fromhex("52900000"), STEP))
            fuori.append((_tabella_profili(profile_keys), STEP))
            profile_keys = None               # una volta sola

        if payload[:2] == b"\x51\x20":
            payload = _con_rimappatura(payload, remaps)

        fuori.append((payload, gap))

        if indicators and payload[:2] == b"\x55\x50":
            fuori.extend(_gruppo_indicatori(indicators))
            indicators = None                 # una volta sola

    return fuori


def invia(reports, verbose=False, timeout_ms=100):
    """Manda la sessione, aspettando per ogni report *il suo* ACK.

    Leggerne uno solo e tenere quello che arriva era la stessa trappola che
    per un giorno ha fatto credere non indirizzabili i quattro LED
    indicatori: il device intercala report non richiesti (`ff aa` stato di
    tasti e rotelle, un `42 20` occasionale) fra un comando e la sua conferma,
    e le letture slittano di uno, poi di due, finche il pad continua ad ACKare
    e smette di eseguire. Qui la deriva conta piu che altrove, perche una
    sessione e lunga oltre centocinquanta report.

    Il fallimento e muto per definizione: se l'eco non arriva entro il
    timeout si va avanti lo stesso — e quello che faceva anche prima — ma
    `verbose` lo dice, ed e l'unico modo di accorgersene senza guardare il pad.
    """
    path = next((d["path"] for d in hid.enumerate(VID, PID)
                 if d.get("usage_page") == 0xFF00), None)
    if path is None:
        raise SystemExit("ControlPad non trovato: e collegato?")
    dev = hid.device()
    dev.open_path(path)
    senza_ack = 0
    try:
        for payload, gap in reports:
            if gap:
                time.sleep(min(gap, 0.5))
            dev.write(bytes([0x00]) + payload[:REPORT].ljust(REPORT, b"\0"))
            if attendi_ack(dev, payload[:2], timeout_ms) is None:
                senza_ack += 1
                if verbose:
                    print(f"  nessun ACK per {payload[:4].hex()}")
    finally:
        dev.close()
    if verbose:
        print(f"inviati {len(reports)} report, {senza_ack} senza ACK")
    return senza_ack


def scrivi(macros=(), remaps=None, lighting=None, profile_keys=None,
           indicators=None, verbose=False):
    """Scorciatoia: costruisce e invia in un colpo solo.

    Restituisce quanti report non hanno ricevuto la loro conferma: zero e
    l'unico valore che dice davvero che la scrittura e passata tutta.
    """
    return invia(costruisci(macros, remaps, lighting, profile_keys, indicators),
                 verbose)
