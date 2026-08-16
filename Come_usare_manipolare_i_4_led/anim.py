"""Sixteen finished effects for the four indicator LEDs.

Doubles as the worked example for effetti.py: every effect below is a few
lines built out of those primitives, and each one is annotated with the
technique it demonstrates, so the file can be read top to bottom as a tour of
what the library is for.

    python anim.py            rassegna: tutti e sedici, in fila
    python anim.py cometa     uno solo, a ciclo continuo, per tararlo
    python anim.py bench      quanti aggiornamenti al secondo regge il canale

The pieces they are made of, and the reasoning behind them, are in
ANIMAZIONI.md.
"""

import sys
import pathlib

# Driver e primitive stanno nel motore, che e anche cio che l'app impacchetta:
# tenerne una copia qui accanto significherebbe correggere ogni cosa due volte.
# Il percorso va aggiunto in coda e non in testa, cosi un modulo omonimo di
# questa cartella resta quello che vince.
_MOTORE = str(pathlib.Path(__file__).resolve().parent.parent / "ControlPadEngine")
if _MOTORE not in sys.path:
    sys.path.append(_MOTORE)

from controlpad import ControlPad          # noqa: E402
import effetti as fx                       # noqa: E402

DURATA = 3.5        # quanto resta in scena ogni effetto della rassegna
STACCO = 0.35       # buio fra un effetto e il successivo, per separarli


# --- movimento ------------------------------------------------------------
# Tutti costruiti su percorso(), che tiene la posizione come numero reale.
# Il verso, la velocita' e il punto di partenza sono suoi parametri: sono
# quelle tre manopole a distinguere gli effetti di questo gruppo.

def rincorsa(t):
    """percorso + scia: la coda dietro la testa dice dove si sta andando."""
    pos = fx.percorso(t, giri_al_secondo=1.4)
    return fx.dipingi(fx.scia(pos, lunghezza=1.6), fx.hsv(t * 0.3))


def cometa(t):
    """strati: testa bianca sopra una coda calda, due livelli sovrapposti."""
    pos = fx.percorso(t, giri_al_secondo=1.1)
    coda = fx.dipingi(fx.scia(pos, lunghezza=2.2, forma=fx.entra), fx.hsv(0.07))
    return fx.strati(coda, fx.punto(pos, (255, 245, 220)))


def arrivo(t):
    """verso=SINISTRA: stesso effetto, ma entra da destra invece che da sinistra."""
    pos = fx.percorso(t, giri_al_secondo=1.1, verso=fx.SINISTRA)
    return fx.dipingi(fx.scia(pos, lunghezza=1.6, verso=fx.SINISTRA),
                      fx.hsv(0.45))


def pendolo(t):
    """circolare=False: i capi sono estremi veri, quindi torna indietro."""
    pos = fx.seno(fx.fase(t, 1.8)) * (fx.N - 1)
    return fx.punto(pos, fx.hsv(0.0), circolare=False)


def riempimento(t):
    """barra con riempimento parziale: un livello continuo su quattro passi."""
    return fx.dipingi(fx.barra(fx.pingpong(fx.fase(t, 2.4)) * fx.N),
                      fx.hsv(0.45))


def onda(t):
    """sfasamento per indice: la stessa onda letta in quattro punti diversi."""
    return [fx.gamma(fx.hsv(0.75, 1.0, fx.seno(fx.fase(t, 1.1) - i * 0.16)))
            for i in range(fx.N)]


# --- colore ---------------------------------------------------------------
# Qui non si muove niente: cambia la tinta o la luminosita'. E' il gruppo in
# cui la correzione gamma si vede di piu', perche' le rampe sono lente e
# attraversano tutta la parte bassa della curva.

def arcobaleno(t):
    """tinta che deriva: h e' circolare, quindi puo' crescere all'infinito."""
    return [fx.hsv(t * 0.35 + i * 0.12) for i in range(fx.N)]


def respiro(t):
    """seno + gamma: senza la correzione sembrerebbe crollare alla fine."""
    return [fx.gamma(fx.hsv(0.55, 1.0, fx.seno(fx.fase(t, 3.0))))] * fx.N


def battito(t):
    """due impulsi sfalsati nello stesso giro: il ritmo di un battito."""
    v = max(fx.impulso(fx.fase(t, 1.1), 0.16),
            fx.impulso(fx.fase(t, 1.1) - 0.22, 0.16))
    return [fx.gamma(fx.hsv(0.98, 1.0, v))] * fx.N


def brace(t):
    """rumore sfasato per indice: in fase sembrerebbe un guasto, non fuoco."""
    return [fx.gradiente(fx.FUOCO, 0.35 + 0.55 * fx.rumore(t * 0.6 + i * 3.1))
            for i in range(fx.N)]


# scintille tiene memoria fra un fotogramma e l'altro, quindi va costruita
# una volta sola: con_decadimento restituisce una chiusura con dentro lo stato.
scintille = fx.con_decadimento(fx.casuale(probabilita=0.06), tenuta=0.88)
scintille.__doc__ = """casuale + con_decadimento: accensioni brusche rese
morbide da una coda temporale."""


# --- segnalazione ---------------------------------------------------------
# Effetti che devono comunicare qualcosa, non decorare. Sono volutamente
# leggibili a colpo d'occhio: forme d'onda squadrate, colori convenzionali.

def allarme(t):
    """quadra: solo acceso o spento, nessuna sfumatura da interpretare."""
    return [fx.hsv(0.0, 1.0, fx.quadra(fx.fase(t, 0.22)))] * fx.N


def polizia(t):
    """le due meta' in controtempo: stessa onda, una negata rispetto all'altra."""
    acceso = fx.quadra(fx.fase(t, 0.34))
    return [fx.hsv(0.62, 1.0, acceso) if i < 2 else fx.hsv(0.0, 1.0, 1 - acceso)
            for i in range(fx.N)]


notifica = fx.in_sequenza(
    (lambda t: [fx.hsv(0.5, 0.35, fx.impulso(t / 0.18))] * fx.N, 0.18),
    (lambda t: [fx.NERO] * fx.N, 0.10),
    (lambda t: [fx.hsv(0.5, 0.35, fx.impulso(t / 0.18))] * fx.N, 0.18),
    (lambda t: [fx.NERO] * fx.N, 0.25),
    (lambda t: [fx.hsv(0.5, 1.0, 0.25 * fx.seno(fx.fase(t, 2.0)))] * fx.N, 2.0),
)
notifica.__doc__ = """in_sequenza: due lampi, una pausa, poi uno stato di
attesa discreto. Un'animazione con inizio, centro e fine."""


def vu_meter(t):
    """colora: la tinta dipende dalla posizione, non dal tempo.

    E' quello che serve a un indicatore: l'ultimo LED resta rosso qualunque
    sia il livello, perche' e' la posizione a portare l'informazione.
    """
    livello = fx.N * fx.seno(fx.fase(t, 2.2)) * (0.75 + 0.25 * fx.rumore(t * 4))
    return fx.colora(fx.barra(livello), fx.VU)


def profilo(t):
    """barra a scalini: qui i quattro LED sono quattro cose distinte.

    Senza riempimento parziale, perche' un profilo e' intero o non e': un LED
    a meta' direbbe qualcosa che non esiste. Scorre i quattro profili lungo
    DURATA, quindi va riprodotto per quel tempo o per un suo multiplo.
    """
    attivo = int(fx.fase(t, DURATA) * 4) + 1
    return fx.dipingi(fx.barra(attivo, parziale=False), fx.hsv(0.5))


def countdown(t):
    """due fasi in una: lo scalare, e poi il lampeggio d'arrivo.

    Non e' ciclico: il conto alla rovescia occupa i primi otto decimi di
    DURATA e il resto lampeggia, quindi va riprodotto esattamente per quel
    tempo, non piu' a lungo.
    """
    corsa = t / (DURATA * 0.78)
    if corsa < 1.0:
        return fx.dipingi(fx.barra(fx.N * (1 - corsa), parziale=False),
                          fx.hsv(0.28))
    return [fx.hsv(0.0, 1.0, fx.quadra(fx.fase(t, 0.16)))] * fx.N


RASSEGNA = [
    ("rincorsa", rincorsa, "percorso + scia"),
    ("cometa", cometa, "strati: testa sopra la coda"),
    ("arrivo", arrivo, "verso=SINISTRA, entra da destra"),
    ("pendolo", pendolo, "circolare=False, torna indietro"),
    ("riempimento", riempimento, "barra con livello parziale"),
    ("onda", onda, "sfasamento per indice"),
    ("arcobaleno", arcobaleno, "tinta che deriva nel tempo"),
    ("respiro", respiro, "seno + correzione gamma"),
    ("battito", battito, "due impulsi in un giro"),
    ("brace", brace, "rumore sfasato + palette FUOCO"),
    ("scintille", scintille, "casuale + coda temporale"),
    ("allarme", allarme, "onda quadra, nessuna sfumatura"),
    ("polizia", polizia, "due meta' in controtempo"),
    ("notifica", notifica, "in_sequenza: inizio, centro, fine"),
    ("vu_meter", vu_meter, "colora: tinta per posizione"),
    ("profilo", profilo, "barra a scalini, quattro stati"),
    ("countdown", countdown, "due fasi nello stesso effetto"),
]

EFFETTI = {nome: funzione for nome, funzione, _ in RASSEGNA}


def rassegna(pad):
    """Tutti gli effetti in fila, con uno stacco al buio fra l'uno e l'altro."""
    for n, (nome, effetto, tecnica) in enumerate(RASSEGNA, 1):
        print(f"{n:2}/{len(RASSEGNA)}  {nome:<12} {tecnica}")
        _, _, saltati = fx.riproduci(pad, effetto, DURATA, fps=60)
        if saltati:
            print(f"        {saltati} fotogrammi oltre il ritmo del canale")
        fx.fissa(pad, [fx.NERO] * fx.N, STACCO)


def a_ciclo(pad, nome):
    """Un solo effetto ripetuto finche' non si interrompe: serve per tararlo."""
    effetto = EFFETTI[nome]
    print(f"{nome} a ciclo continuo, Ctrl-C per fermare")
    print((effetto.__doc__ or "").strip())
    while True:
        fx.riproduci(pad, effetto, DURATA, fps=60)


def bench(pad):
    """Quanti aggiornamenti al secondo regge, senza attese artificiali."""
    for commit, etichetta in ((True, "con commit 41 80"), (False, "senza commit")):
        n, sec, _ = fx.riproduci(pad, lambda t: [fx.hsv(t)] * fx.N,
                                 durata=2.0, fps=10_000, commit=commit)
        print(f"  {etichetta:<18} {n / sec:5.0f} al secondo "
              f"({sec / n * 1000:.2f} ms per fotogramma)")


if __name__ == "__main__":
    scelta = sys.argv[1] if len(sys.argv) > 1 else None

    if scelta and scelta not in EFFETTI and scelta != "bench":
        print(f"'{scelta}' non esiste. Disponibili:")
        for nome, _, tecnica in RASSEGNA:
            print(f"  {nome:<12} {tecnica}")
        raise SystemExit(1)

    with ControlPad() as pad:
        try:
            if scelta == "bench":
                bench(pad)
            elif scelta:
                a_ciclo(pad, scelta)
            else:
                rassegna(pad)
        except KeyboardInterrupt:
            print()
        finally:
            fx.fissa(pad, [fx.BIANCO] * fx.N)
            print("ripristinati bianchi")
