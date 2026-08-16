"""Disposizione fisica del ControlPad e conversioni fra i suoi tre indici.

Il dispositivo usa tre numerazioni diverse per le stesse ventiquattro cose, ed
e la fonte di errore piu insidiosa del protocollo:

* il **codice HID di default** identifica il tasto nei comandi di rimappatura
  e nell'assegnazione delle macro (il pad emula la porzione sinistra di una
  tastiera QWERTY, e quel codice e la lettera che il tasto batterebbe);
* l'**indice per colonne** vale per i LED e per la tabella dei profili;
* l'**indice per righe** vale per l'ordine di caricamento della keymap.

L'ultima riga ha quattro tasti perche lo spazio ne occupa due posizioni: in
totale 24 tasti su una griglia di 25 posizioni.
"""

RIGHE, COLONNE = 5, 5

# Codici HID di default, riga per riga, come li carica la keymap.
GRIGLIA = [
    [0x35, 0x1E, 0x1F, 0x20, 0x21],   # `  1  2  3  4
    [0x2B, 0x14, 0x1A, 0x08, 0x15],   # Tab  q  w  e  r
    [0x39, 0x04, 0x16, 0x07, 0x09],   # Caps a  s  d  f
    [0xE1, 0x1D, 0x1B, 0x06, 0x19],   # Shift z  x  c  v
    [0xE0, 0xC0, 0xE2, 0x2C, None],   # Ctrl  ·  Alt  [ spazio ]
]

NOMI = {
    0x35: "`", 0x1E: "1", 0x1F: "2", 0x20: "3", 0x21: "4",
    0x2B: "Tab", 0x14: "q", 0x1A: "w", 0x08: "e", 0x15: "r",
    0x39: "Caps", 0x04: "a", 0x16: "s", 0x07: "d", 0x09: "f",
    0xE1: "Shift", 0x1D: "z", 0x1B: "x", 0x06: "c", 0x19: "v",
    0xE0: "Ctrl", 0xC0: "·", 0xE2: "Alt", 0x2C: "Spazio",
}

# Le due rotelle compaiono come pseudo-tasti, una coppia per verso.
ROTELLA_SINISTRA = (0xC6, 0xC7)
ROTELLA_DESTRA = (0xF5, 0xF6)

PRIMO_LED_GRIGLIA = 4      # i primi quattro indici sono i LED indicatori


def tasto(riga, colonna):
    """Codice HID del tasto in posizione (riga, colonna), entrambe da 1."""
    return GRIGLIA[riga - 1][colonna - 1]


def indice_colonne(riga, colonna):
    """Indice per colonne: numerazione di LED e tabella profili."""
    return (colonna - 1) * RIGHE + (riga - 1)


def indice_led(riga, colonna):
    """Indice del LED sotto quel tasto, nella tabella dei colori."""
    return PRIMO_LED_GRIGLIA + indice_colonne(riga, colonna)


def posizione(codice_hid):
    """(riga, colonna) del tasto con quel codice HID, entrambe da 1."""
    for r, riga in enumerate(GRIGLIA, 1):
        for c, k in enumerate(riga, 1):
            if k == codice_hid:
                return r, c
    raise KeyError(f"codice tasto sconosciuto: 0x{codice_hid:02x}")


def tasto_da_indice_colonne(indice):
    """Il contrario di indice_colonne: serve per la tabella dei profili.

    L'indice 24 e l'unico dei venticinque a non avere un tasto: e la posizione
    che lo spazio occupa senza esserci. Restituire None faceva cadere il
    chiamante piu tardi e altrove, con un messaggio che non c'entrava niente.
    """
    if not 0 <= indice < RIGHE * COLONNE:
        raise KeyError(f"indice per colonne fuori dalla griglia: {indice}")
    colonna, riga = divmod(indice, RIGHE)
    codice = GRIGLIA[riga][colonna]
    if codice is None:
        raise KeyError(f"l'indice {indice} non ha un tasto: "
                       "e la seconda posizione dello spazio")
    return codice


def tutti_i_tasti():
    """I 24 codici HID, in ordine di riga."""
    return [k for riga in GRIGLIA for k in riga if k is not None]
