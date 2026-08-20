#!/usr/bin/env python3
"""I quattro LED indicatori, banco per banco, guardandoli.

Perche serve guardarli. Il registro degli indicatori (`0x00fc`) si rilegge
identico su tutti i banchi: scritto rosso-verde-blu-bianco sul banco 1, sul 3 e
sul 7, `55 40 fc 00 0c` restituisce ogni volta quello che ci si e messo. Quindi
la scrittura *arriva*. Se poi i LED non lo mostrano, a cambiare le carte in
tavola e qualcosa fra il registro e i diodi — la modalita di illuminazione
attiva su quel banco, o il firmware che se li riprende per segnalare il profilo
— e quella differenza non si vede da nessuna rilettura.

Il programma scrive un motivo inconfondibile e si ferma ad aspettare. Non
serve ricordarsi niente: basta rispondere se i LED lo mostrano oppure no.

    python3 prova_led.py

Non scrive in flash: tocca solo il registro degli indicatori e il banco
attivo. Alla fine rimette il banco di partenza e i LED bianchi.

Chiudi ControlPad.app prima di lanciarlo: su macOS il pad lo tiene un processo
solo, e con l'app aperta qui non si apre niente.
"""

import sys
import time

import hid

from controlpad import ControlPad, VID, PID
import effects

MOTIVO = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255)]
NOME_MOTIVO = "1 ROSSO · 2 VERDE · 3 BLU · 4 BIANCO"
SPENTI = [(0, 0, 0)] * 4
BANCHI = [1, 3, 7, 15]

# In automatico ogni banco prende un colore pieno tutto suo: cosi chi guarda
# riferisce *cosa* ha visto invece di cronometrare, e un banco che non risponde
# si riconosce da solo senza tenere il conto dei secondi.
TINTE = {1: ("ROSSO", (255, 0, 0)), 3: ("VERDE", (0, 255, 0)),
         7: ("BLU", (0, 0, 255)), 15: ("VIOLA", (160, 0, 255))}


def automatico(secondi=10.0):
    """Come main(), ma senza domande: si guarda e si riferisce dopo."""
    partenza = _banco()
    for banco in BANCHI:
        nome_tinta, tinta = TINTE[banco]
        _vai(banco)
        _scrivi(SPENTI)
        time.sleep(1.0)
        _scrivi([tinta] * 4)
        letti = _leggi()
        slot, nome = _modalita()
        print(f"  profilo {banco + 1:<2} (banco {banco:<2})  ->  {nome_tinta:<6}"
              f"  modalita={nome:<16} riletto="
              f"{'identico' if letti == [tinta] * 4 else letti}", flush=True)
        time.sleep(secondi)
    _vai(partenza if partenza is not None else 0)
    _scrivi([(255, 255, 255)] * 4)
    print("\nfine — i LED sono tornati bianchi e il banco di partenza "
          f"({partenza}) e ripristinato.", flush=True)


def _banco():
    with ControlPad() as pad:
        risposta = pad._send(bytes([0x52, 0x00, 0x00, 0x00]), "banco")
    return risposta[4] if risposta else None


def _modalita():
    with ControlPad() as pad:
        risposta = pad._send(bytes([0x52, 0x28, 0x00, 0x00]), "modalita")
    if risposta is None:
        return None, "?"
    slot = risposta[4]
    if slot >= len(effects.SLOT_ORDER):
        # 0xff e il residuo del comando di applicazione, non una modalita.
        return slot, "nessuna (appena applicato)"
    return slot, effects.SLOT_ORDER[slot]


def _vai(banco):
    with ControlPad() as pad:
        pad.set_profile(banco)
    time.sleep(0.4)


def _scrivi(colori):
    with ControlPad() as pad:
        pad.set_indicators(colori, commit=True)
    time.sleep(0.2)


def _leggi():
    with ControlPad() as pad:
        return pad.read_indicators()


def main():
    if not any(d.get("usage_page") == 0xFF00 for d in hid.enumerate(VID, PID)):
        print("Pad non collegato.")
        return 1
    try:
        partenza = _banco()
    except Exception as exc:
        print(f"Device occupato ({exc}).\n"
              "Chiudi ControlPad.app: su macOS il pad lo tiene un processo solo.")
        return 1

    if "--auto" in sys.argv:
        print("Guarda i QUATTRO LED SOPRA il pad. Un colore per profilo.\n")
        automatico()
        return 0

    print(__doc__.split("\n\n")[0])
    print(f"\nBanco di partenza: {partenza}. Provo i banchi {BANCHI}.\n")
    print("Guarda i QUATTRO LED SOPRA il pad, non quelli sotto i tasti.\n")

    esiti = {}
    for banco in BANCHI:
        _vai(banco)
        slot, nome = _modalita()
        # Prima spenti, poi il motivo: cosi anche "non e cambiato niente" si
        # distingue da "era gia cosi".
        _scrivi(SPENTI)
        time.sleep(0.8)
        _scrivi(MOTIVO)
        letti = _leggi()

        print(f"--- banco {banco}  (profilo {banco + 1}) ---")
        print(f"    modalita di illuminazione del banco: {nome}")
        print(f"    scritto:  {NOME_MOTIVO}")
        print(f"    riletto:  {'identico' if letti == MOTIVO else letti}")
        risposta = input("    I LED mostrano questo motivo? [s/n] ").strip().lower()
        esiti[banco] = risposta in ("s", "si", "sì", "y", "yes")
        print()

    _vai(partenza if partenza is not None else 0)
    _scrivi([(255, 255, 255)] * 4)

    print("=" * 60)
    for banco, visto in esiti.items():
        print(f"  profilo {banco + 1:<2} (banco {banco:<2}): "
              f"{'MOSTRA' if visto else 'NON mostra'}")

    visti = [b for b, v in esiti.items() if v]
    if len(visti) == len(esiti):
        print("\nI LED rispondono su tutti i banchi: il registro e i diodi sono a\n"
              "posto, e la differenza che vedi nell'app viene da cosa l'app\n"
              "manda, non da cosa il pad accetta.")
    elif not visti:
        print("\nI LED non rispondono su nessun banco, nemmeno riletti identici:\n"
              "il registro non comanda i diodi da solo, serve altro.")
    else:
        print(f"\nI LED rispondono solo sui banchi {visti}. E la prova che il banco\n"
              "attivo cambia cosa il registro degli indicatori riesce a mostrare:\n"
              "confronta la riga 'modalita di illuminazione' dei banchi che\n"
              "funzionano con quella di chi non funziona.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
