"""Codifica delle macro: testo e combinazioni di tasti in eventi da 4 byte.

Una macro e una sequenza di eventi, uno per ogni pressione o rilascio:

    [codice HID] [tipo] [ritardo lo] [ritardo hi]

dove il tipo e 3c per la pressione e 5c per il rilascio, e il ritardo e in
millisecondi su 16 bit. I modificatori non sono speciali: sono tasti normali
col loro codice HID, quindi scrivere "A" sono quattro eventi.

La lista finisce sempre con il terminatore 00 fc fe ff.
"""

REPORT = 64

LSHIFT, LCTRL, LALT, LGUI = 0xE1, 0xE0, 0xE2, 0xE3
ESC, DEL, TAB, INVIO, SPAZIO = 0x29, 0x4C, 0x2B, 0x28, 0x2C
F1 = 0x3A          # i tasti funzione proseguono in ordine: F2 = F1 + 1, ecc.

PRESS, RELEASE = 0x3C, 0x5C
TERMINATOR = bytes.fromhex("00fcfeff")

# carattere -> (codice HID, richiede shift). La punteggiatura segue il layout
# italiano: '|' e Shift piu il tasto a sinistra dell'1, non Shift-0x31.
CHARS = {c: (0x04 + i, False) for i, c in enumerate("abcdefghijklmnopqrstuvwxyz")}
CHARS.update({c.upper(): (0x04 + i, True)
              for i, c in enumerate("abcdefghijklmnopqrstuvwxyz")})
CHARS.update({d: (0x1E + i, False) for i, d in enumerate("1234567890")})
CHARS.update({" ": (0x2C, False), "!": (0x1E, True),
              "|": (0x35, True), "\\": (0x35, False),
              "<": (0x64, False), ">": (0x64, True)})


class EventList:
    """Costruisce il flusso di eventi, una voce per pressione o rilascio."""

    def __init__(self):
        self.buf = bytearray()

    def press(self, usage, delay):
        self.buf.extend([usage, PRESS, delay & 0xFF, delay >> 8])

    def release(self, usage, delay):
        self.buf.extend([usage, RELEASE, delay & 0xFF, delay >> 8])

    def tap(self, usage, hold, gap):
        self.press(usage, hold)
        self.release(usage, gap)

    def done(self):
        return bytes(self.buf) + TERMINATOR


def events_for(text, hold=30, gap=30, shift_settle=50):
    """Digita un testo, tenendo premuto shift sui gruppi di maiuscole.

    Rilasciare e ripremere shift per ogni maiuscola triplicherebbe gli eventi
    in una parola come "CIA" e darebbe al sistema piu occasioni di vedere il
    modificatore e la lettera fuori ordine, quindi shift resta giu per tutto
    il gruppo.
    """
    ev = EventList()
    shift_down = False

    for ch in text:
        if ch not in CHARS:
            raise ValueError(f"carattere non mappato: {ch!r}")
        usage, needs_shift = CHARS[ch]

        if needs_shift and not shift_down:
            ev.press(LSHIFT, shift_settle)
            shift_down = True
        elif not needs_shift and shift_down:
            ev.release(LSHIFT, shift_settle)
            shift_down = False

        ev.tap(usage, hold, gap)

    if shift_down:
        ev.release(LSHIFT, shift_settle)
    return ev.done()


def events_for_combo(usages, stagger=10, hold=20):
    """Combinazione, premuta come la premerebbe una persona.

    I modificatori scendono uno alla volta a qualche millisecondo di distanza,
    il tasto finale arriva mentre sono tutti ancora premuti, poi si rilascia
    tutto insieme. Rilasciare un modificatore prima del tasto annullerebbe la
    combinazione, riducendola a pressioni separate.
    """
    ev = EventList()
    for u in usages[:-1]:
        ev.press(u, stagger)
    ev.press(usages[-1], hold)
    for u in reversed(usages):
        ev.release(u, 0)
    return ev.done()


def macro_packets(body):
    """Divide il flusso su piu report: 53 <continuazione> <eventi> 00.

    Il secondo byte dice se il report apre una macro (00) o ne continua una
    (01): un 00 azzera quanto accumulato. Con due soli report — l'unico caso
    presente nelle catture dell'app — questo e indistinguibile da un indice di
    blocco o da un marcatore di fine; entrambe quelle letture sono state
    provate e conservavano solo due report di eventi, la prima coppia o
    l'ultima.

    Il terzo byte e il numero di eventi in *questo* report, non il totale. La
    fine della macro la segna il terminatore, non l'intestazione.
    """
    room = REPORT - 4
    pieces = [body[i:i + room] for i in range(0, len(body), room)]
    return [bytes([0x53, 0 if i == 0 else 1, len(piece) // 4, 0x00]) + piece
            for i, piece in enumerate(pieces)]
