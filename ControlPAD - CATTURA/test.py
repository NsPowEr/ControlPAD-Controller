"""Test circuit for everything the driver claims to do.

Each phase is run on its own so it can be watched, and each one is designed to
fail visibly rather than ambiguously: colours differ per row, effects are held
long enough to tell apart, and every configured key is lit in a colour that
identifies which behaviour it carries.

    python test.py 1     mappatura LED per righe
    python test.py 2     ciclo degli effetti
    python test.py 3     rimappatura e macro
    python test.py 4     rilettura dopo scollegamento
    python test.py off   spegne tutto
"""

import sys
import time

from controlpad import ControlPad, led_index, EFFECTS, GRID_COLS, GRID_ROWS
from macro import events_for, events_for_combo, LCTRL

ROSSO, VERDE, BLU = (255, 0, 0), (0, 255, 0), (0, 0, 255)
GIALLO, MAGENTA = (255, 200, 0), (255, 0, 255)
ARANCIO, VIOLA, CIANO, BIANCO = (255, 90, 0), (150, 0, 255), (0, 220, 255), (255, 255, 255)

RIGHE = [ROSSO, VERDE, BLU, GIALLO, MAGENTA]
NOMI_RIGHE = ["ROSSO", "VERDE", "BLU", "GIALLO", "MAGENTA"]

KEY_1_1, KEY_2_2, KEY_3_3, KEY_3_4 = 0x35, 0x1A, 0x16, 0x07


def fase1():
    """Righe di colore diverso: verifica l'asse che il test a colonne non copriva."""
    print("FASE 1 — mappatura LED per righe")
    for r, nome in enumerate(NOMI_RIGHE):
        print(f"  riga {r + 1} -> {nome}")
    with ControlPad() as pad:
        pad.set_grid({(c, r): RIGHE[r]
                      for c in range(GRID_COLS) for r in range(GRID_ROWS)})


def fase2(hold=8):
    """Ogni effetto tenuto abbastanza da distinguerlo dal precedente."""
    print(f"FASE 2 — {len(EFFECTS)} effetti, {hold} s ciascuno "
          f"(totale {len(EFFECTS) * hold} s)")
    with ControlPad() as pad:
        for n, (eff, speed) in enumerate(EFFECTS, 1):
            print(f"  [{n}/{len(EFFECTS)}] effetto 0x{eff:02x}  velocita 0x{speed:02x}",
                  flush=True)
            pad.set_effect(eff, 255, 255, 255, speed=speed)
            time.sleep(hold)
    print("  fine ciclo")


def fase3():
    """Rimappatura e tre macro diverse, ognuna su un tasto di colore distinto."""
    from session import scrivi

    piano = [
        (0x08, KEY_2_2, events_for("test"), "test"),
        (0x09, KEY_3_3, events_for("CIAo FighEtta|1|1|"), "fighetta"),
        (0x0a, KEY_3_4, events_for_combo([LCTRL, 0x04]), "ctrla"),
    ]
    remaps = {KEY_1_1: 0x1B}          # (1,1) diventa il tasto x

    print("FASE 3 — rimappatura e macro")
    print(f"  (1,1) bianco   -> rimappato sul tasto x")
    scrivi(macros=piano, remaps=remaps)

    with ControlPad() as pad:
        pad.set_leds({led_index(0, 0): BIANCO,
                      led_index(2, 1): CIANO,
                      led_index(2, 2): ARANCIO,
                      led_index(3, 2): VIOLA})


def fase4():
    """Dopo scollegamento e ricollegamento non si scrive nulla: si guarda."""
    print("FASE 4 — nessun comando inviato.")
    print("  Stacca il pad, riattaccalo e ricontrolla i quattro tasti della fase 3.")
    print("  Se restano configurati, l'intera configurazione vive nel firmware.")


def fase5():
    """Colore scritto nel profilo anziché solo dal vivo, per sopravvivere allo spegnimento."""
    from session import scrivi

    piano = [
        (0x08, KEY_2_2, events_for("test"), "test"),
        (0x09, KEY_3_3, events_for("CIAo FighEtta|1|1|"), "fighetta"),
        (0x0a, KEY_3_4, events_for_combo([LCTRL, 0x04]), "ctrla"),
    ]
    verde_acido = (0x01, 0x00, 60, 255, 0, 255)   # effetto statico, colore inconfondibile

    print("FASE 5 — colore salvato nel profilo")
    print("  verde acido statico, scritto nel blob di profilo invece che dal vivo")
    scrivi(macros=piano, remaps={KEY_1_1: 0x1B}, lighting=verde_acido)
    print("  ora stacca e riattacca: se resta verde, il colore e persistente")


def fase6():
    """L'ultima validazione con il pad collegato: tutto cio che non era mai stato eseguito.

    Tre cose insieme, ognuna su una riga sua e con un colore che la identifica:
    sei macro (piu dei quattro gruppi che aveva la cattura di partenza),
    cinque funzioni speciali, e due tasti selettori di profilo.
    """
    from session import scrivi, FUNZIONI

    # (riga, colonna) -> codice HID di default del tasto
    R1 = [0x35, 0x1e, 0x1f, 0x20, 0x21]
    R2 = [0x2b, 0x14, 0x1a, 0x08, 0x15]
    R3 = [0x39, 0x04, 0x16, 0x07, 0x09]
    R4 = [0xe1, 0x1d, 0x1b, 0x06, 0x19]

    parole = ["uno", "due", "tre", "quattro", "cinque", "sei"]
    tasti_macro = R1 + [R2[0]]
    macros = [(8 + i, tasti_macro[i], events_for(p), p)
              for i, p in enumerate(parole)]

    funzioni = {
        R3[0]: FUNZIONI["volume_su"],
        R3[1]: FUNZIONI["volume_giu"],
        R3[2]: FUNZIONI["play_pausa"],
        R3[3]: FUNZIONI["effetto_avanti"],
        R3[4]: FUNZIONI["luce_su"],
    }
    # indici per colonne: (colonna, riga) -> colonna*5 + riga
    profili = {0 * 5 + 3: 0, 1 * 5 + 3: 1}

    print("FASE 6 — validazione finale")
    print(f"  {len(macros)} macro (la cattura di partenza ne aveva 4)")
    print(f"  {len(funzioni)} funzioni speciali — mai eseguite prima")
    print(f"  {len(profili)} tasti selettori di profilo — mai eseguiti prima")
    scrivi(macros=macros, remaps=funzioni, profile_keys=profili, verbose=True)

    with ControlPad() as pad:
        colori = {}
        for c in range(5):
            colori[led_index(c, 0)] = VERDE          # riga 1: macro
        colori[led_index(0, 1)] = VERDE              # riga 2 col 1: sesta macro
        for c in range(5):
            colori[led_index(c, 2)] = CIANO          # riga 3: funzioni
        for c in range(2):
            colori[led_index(c, 3)] = GIALLO         # riga 4: profili
        pad.set_leds(colori)
    print("  verde = macro | ciano = funzioni | giallo = profili")


def spegni():
    with ControlPad() as pad:
        pad.set_leds({})
    print("tutti i LED spenti")


if __name__ == "__main__":
    fasi = {"1": fase1, "2": fase2, "3": fase3, "4": fase4, "5": fase5, "6": fase6,
            "off": spegni}
    scelta = sys.argv[1] if len(sys.argv) > 1 else ""
    if scelta not in fasi:
        print(__doc__)
        sys.exit(1)
    fasi[scelta]()
