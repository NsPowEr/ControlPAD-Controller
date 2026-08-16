"""Le 14 modalità di illuminazione del ControlPad, decodificate dalle catture.

Ricavate da `captures/16_tutti_gli_effetti.pcapng`, dove il software ufficiale
è stato fatto scorrere lungo tutta la sua lista di modalità. L'attribuzione dei
nomi non è un'ipotesi libera: regge su tre riscontri indipendenti.

* **Ordine.** Le selezioni nella cattura seguono esattamente, dalla prima
  all'ultima, l'ordine della lista mostrata dall'app.
* **Partizione.** La tabella `56 15` che l'app invia dichiara per ogni slot un
  "tipo" (1 o 2): otto slot di tipo 1 e sei di tipo 2. Le modalità osservate si
  dividono esattamente così — otto usano la forma di comando corta, sei quella
  lunga.
* **Marcatori.** Due slot hanno un marcatore unico nella tabella `56 15`:
  `bbbbbbbb` allo slot 04 e `aaaaaaaa` allo slot 0d. Nella cattura quegli stessi
  marcatori compaiono nell'handshake esattamente davanti a Personalizza e a
  Spegni, che nella lista dell'app stanno in quinta e in quattordicesima
  posizione.

Le tre modalità già confermate in precedenza sul dispositivo (Statico `0x01`,
Lampeggio `0x30`, Ciclo colore `0x31`) cadono al posto giusto, il che chiude il
cerchio.

## Le due forme di comando

**Tipo 1** — otto modalità, un colore solo:

    56 83 00 00 | 01 00 00 00 | 00 <id> 00 c1 | <vel> 00 00 00 | R G B A | <parametri>

**Tipo 2** — sei modalità, tutte reattive al tocco, **due colori**:

    56 83 00 00 | <len> 00 <len> 00 | 03 00 00 00 | … | R G B A (off 24) |
    … | <vel> (off 36) | R G B A (off 40) | …

Il secondo colore è la ragione per cui queste modalità hanno due selettori
nell'app: sono effetti che reagiscono alla pressione, quindi hanno un colore di
fondo e uno di reazione. `<len>` è la lunghezza del payload in parole da 4 byte
(0x0b–0x0d), non un numero di slot.

Il quarto byte del colore è la luminosità: nelle catture varia da sola mentre
si trascina il cursore, RGB fermo.

Ogni modalità porta con sé l'intero report registrato dall'app e ne sostituisce
solo i campi che l'utente controlla. È lo stesso metodo che ha funzionato per
le macro: partire dai byte reali invece di ricostruirli, perché il dispositivo
ignora in silenzio le sequenze che non riconosce.
"""

from collections import namedtuple

# offsets: dove stanno colore, velocità e secondo colore dentro il report
Mode = namedtuple("Mode", "key name handshake command color1 color2 speed")

_T1 = dict(color1=16, color2=None, speed=12)
_T2 = dict(color1=24, color2=40, speed=36)

HS_T1 = "56810000010000000100000055555555"
HS_T2 = "56810000020000000100000000000000"
HS_T2B = "56810000020000000200000000000000"   # Stelle e Neve: byte 8 = 02
HS_CUSTOM = "568100000100000002000000bbbbbbbb"
HS_OFF = "568100000100000001000000aaaaaaaa"


def _mode(key, name, hs, cmd, **off):
    return Mode(key, name, bytes.fromhex(hs), bytes.fromhex(cmd),
                off["color1"], off["color2"], off["speed"])


MODES = [
    _mode("static", "Statico", HS_T1,
          "5683000001000000000100c1000000003cff00ff", **_T1),
    _mode("rainbowWave", "Onda arcobaleno", HS_T1,
          "5683000001000000003200c107000000ffffffff00000600000408", **_T1),
    _mode("crosshair", "Mirino", HS_T2,
          "568300000c000c000300000007000100000100c100000000000000ff00000000"
          "008000800b100000ffffffff0000020103000000ffffffffffffffff", **_T2),
    _mode("reactiveFade", "Dissolvenza reattiva", HS_T2,
          "568300000c000c000300000007000100000100c1000000000000c6ff00000000"
          "008000800b100000ffffffff0000020000000000ffffffffffffffff", **_T2),
    # Personalizza non passa di qui: è la tabella per-tasto (set_leds).
    _mode("stars", "Stelle", HS_T2B,
          "568300000d000d000300000007000100000100c100000000000000ff00000000"
          "0040008008100000ffffffff000001000110080110000000ffffffffffffffff", **_T2),
    _mode("snow", "Neve", HS_T2B,
          "568300000d000d000300000007000100000100c100000000000000ff00000000"
          "8140008005100000ffffffff0000030030ff101001400000ffffffffffffffff", **_T2),
    _mode("colorCycle", "Ciclo colore", HS_T1,
          "5683000001000000003100c1080000004000ffff00000300", **_T1),
    _mode("blink", "Lampeggio", HS_T1,
          "5683000001000000003000c10c000000ffffffcc01000400", **_T1),
    _mode("reactivePunch", "Pugno reattivo", HS_T2,
          "568300000b000b000300000007000100000100c100000000000000ff00000000"
          "2880008007100000000000ff00000100ffffffffffffffff", **_T2),
    _mode("circularSpectrum", "Spettro circolare", HS_T1,
          "5683000001000000003400c1040000000000ffff0000fd000080000030001000", **_T1),
    _mode("reactiveTornado", "Tornado reattivo", HS_T1,
          "5683000001000000008300c1040000000000ffff0000fd000080000030001000", **_T1),
    _mode("waterRipple", "Ondulazione di acqua", HS_T2,
          "568300000c000c000300000007000100000100c100000000000000ff00000000"
          "018200800c100000ffffffff0000060000901420ffffffffffffffff", **_T2),
    _mode("off", "Spegni", HS_OFF,
          "5683000001000000100000c1", **_T1),
]

BY_KEY = {m.key: m for m in MODES}


def build(key, color1=None, color2=None, speed=None):
    """(handshake, comando) pronti da inviare.

    color1/color2 sono (r, g, b, luminosità); speed è un byte. Quello che non
    viene passato resta al valore registrato dall'app, che è già valido.

    "custom" è nella tabella dei quattordici slot ma non qui: quello slot non
    è un effetto, è la tabella dei colori per singolo tasto, e si scrive con
    `ControlPad.set_leds`. Chiederlo qui è un errore di chi chiama, e va detto
    invece di uscire con un KeyError che l'app mostrerebbe così com'è.
    """
    if key not in BY_KEY:
        if key in SLOT_ORDER:
            raise ValueError(
                f"la modalità {key!r} non è un comando di effetto: "
                "è la tabella per singolo tasto, usa set_leds/set_grid")
        raise ValueError(f"modalità di illuminazione sconosciuta: {key!r}")

    mode = BY_KEY[key]
    cmd = bytearray(mode.command)

    def put(offset, rgba):
        if offset is None or rgba is None:
            return
        if offset + 4 > len(cmd):
            cmd.extend(bytes(offset + 4 - len(cmd)))
        cmd[offset:offset + 4] = bytes(rgba)

    put(mode.color1, color1)
    put(mode.color2, color2)

    if speed is not None and mode.speed < len(cmd):
        cmd[mode.speed] = speed

    return mode.handshake, bytes(cmd)


# I 14 slot della tabella `56 15`, nell'ordine della lista dell'app. Combacia
# con la colonna "tipo" della tabella (otto 1, sei 2) e con i marcatori unici
# bbbbbbbb / aaaaaaaa, che cadono su Personalizza e Spegni.
SLOT_ORDER = [
    "static", "rainbowWave", "crosshair", "reactiveFade", "custom",
    "stars", "snow", "colorCycle", "blink", "reactivePunch",
    "circularSpectrum", "reactiveTornado", "waterRipple", "off",
]


def describe():
    """Elenco per l'interfaccia: chiave, nome, se ha il secondo colore."""
    return [{"key": m.key, "name": m.name, "dual": m.color2 is not None}
            for m in MODES]
