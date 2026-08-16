"""I quattro colori degli indicatori restano nel pad, o li tiene solo l'host?

La domanda e aperta e le due fonti si contraddicono. ANIMAZIONI.md misura che
il comando dal vivo non scrive in flash e che allo scollegamento i LED tornano
bianchi. Le recensioni del prodotto dicono invece che il software ufficiale
assegna un colore agli indicatori **per profilo**, quindi da qualche parte un
percorso persistente esiste: il candidato e la stessa scrittura `55 50 fc`
mandata dentro la sessione completa, dove la mette l'app ufficiale nella
cattura 12, e non da sola.

Questo script prova le due strade e le fa distinguere. Va lanciato col pad
collegato, in quest'ordine:

    python verifica_persistenza.py vivo        scrive dal vivo e rilegge
    python verifica_persistenza.py sessione    scrive dentro la sessione completa
    ... stacca il pad, riattaccalo, e senza lanciare nient'altro:
    python verifica_persistenza.py leggi       cosa il pad ha davvero adesso

I quattro colori di prova sono scelti per essere inconfondibili a occhio e
irripetibili per caso: se dopo il ciclo di scollegamento `leggi` li ritrova, la
persistenza c'e e va scritto in PROTOCOL.md; se torna bianco, non c'e e il
percorso per profilo del software ufficiale e ancora da decodificare.
"""

import pathlib
import sys

_MOTORE = str(pathlib.Path(__file__).resolve().parent.parent / "ControlPadEngine")
if _MOTORE not in sys.path:
    sys.path.append(_MOTORE)

from controlpad import ControlPad                    # noqa: E402
import session                                       # noqa: E402

PROVA = [(255, 0, 40), (0, 255, 80), (0, 80, 255), (255, 200, 0)]

BIANCO = (255, 255, 255)


def _mostra(etichetta, colori):
    if colori is None:
        print(f"{etichetta}: nessuna risposta dalla rilettura")
        return
    print(f"{etichetta}: " + "  ".join("%02x%02x%02x" % c for c in colori))


def vivo():
    """Comando dal vivo: `41 04` + `55 50 fc 00 0c` + commit, poi rilettura."""
    with ControlPad(verbose=True) as pad:
        pad.set_indicators(PROVA, commit=True)
        _mostra("scritto  ", PROVA)
        _mostra("riletto  ", pad.read_indicators())
    print("\nGuarda i LED: devono essere rosso, verde, blu, ambra.")
    print("Se la rilettura torna i colori scritti ma i LED restano bianchi,")
    print("il device li memorizza e non li mostra — caso diverso da entrambi.")


def sessione():
    """La stessa scrittura dentro l'inquadramento completo dell'app.

    E il punto in cui la mette il software ufficiale: `41 80 · 52 00 · 41 04 ·
    55 50 · 41 80`, dentro la sessione che chiude con commit e apply. Se la
    persistenza dipende da quel contorno, e qui che si vede.
    """
    session.scrivi(indicators=PROVA, verbose=True)
    with ControlPad() as pad:
        _mostra("riletto  ", pad.read_indicators())
    print("\nOra stacca il pad, riattaccalo, e lancia: leggi")


def flash():
    """Scrittura di sessione completa: 24 tasti + 4 indicatori, colori vistosi.

    Serve a rispondere alla domanda che il collegamento su un altro dispositivo
    ha aperto: il pad conserva l'illuminazione in flash, o la tiene solo l'host
    che gliela riscrive? Sul Mac la configurazione "torna da sola" perche a
    riscriverla e l'app alla riconnessione (AppModel.observeConnection), quindi
    per distinguere le due cose l'app va **chiusa**.

    I colori sono per colonna, uno diverso per ognuna: cosi si vede a occhio se
    e tornata la configurazione scritta qui o un'altra qualunque.
    """
    colonne = [(255, 0, 40), (0, 255, 80), (0, 80, 255), (255, 200, 0), (255, 0, 255)]
    perkey = [colonne[i // 5] for i in range(25)]

    session.scrivi(
        lighting={"color1": [255, 0, 40, 255], "color2": [0, 80, 255, 255],
                  "speed": 0, "perkey": perkey},
        indicators=PROVA, verbose=True)

    print("\nScritto. Ora, in quest'ordine:")
    print("  1. chiudi ControlPad.app  (altrimenti riscrive tutto lei)")
    print("  2. scollega il pad e ricollegalo, senza riaprire l'app")
    print("  3. guarda: cinque colonne di colore diverso e i 4 LED accesi?")
    print("     - si   -> la flash conserva, il problema era solo l'app aperta")
    print("     - no   -> l'illuminazione non e persistente e va deciso cosa")
    print("               dire nell'interfaccia")
    print("  4. poi lancia: leggi     (dice cosa il pad ha davvero negli indicatori)")


def leggi():
    """Cosa il pad ha adesso, senza scrivere niente."""
    with ControlPad() as pad:
        colori = pad.read_indicators()
    _mostra("riletto  ", colori)
    if colori is None:
        return
    if [tuple(c) for c in colori] == PROVA:
        print("\nPERSISTENTE: i colori di prova sono sopravvissuti.")
    elif all(tuple(c) == BIANCO for c in colori):
        print("\nNON persistente: tornati bianchi, come dice ANIMAZIONI.md §13.")
    else:
        print("\nAltro: ne' i colori di prova ne' bianco. Copiali in PROTOCOL.md,")
        print("sono lo stato con cui il pad si riaccende.")


def bianchi():
    """Rimette i quattro bianchi di partenza."""
    with ControlPad() as pad:
        pad.set_indicators([BIANCO] * 4, commit=True)
    print("ripristinati bianchi")


PROVE = {"vivo": vivo, "sessione": sessione, "flash": flash,
         "leggi": leggi, "bianchi": bianchi}

if __name__ == "__main__":
    scelta = sys.argv[1] if len(sys.argv) > 1 else None
    if scelta not in PROVE:
        print(__doc__)
        print("prove disponibili: " + ", ".join(PROVE))
        raise SystemExit(1)
    PROVE[scelta]()
