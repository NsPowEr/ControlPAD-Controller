"""Building blocks for animating the four indicator LEDs.

An effect here is a plain function of elapsed time returning four colours.
That single convention is what makes the pieces below composable: waveforms,
easings, spatial mappings and blends all operate on numbers or on lists of
four colours, never on the device, so an effect can be written, layered,
reversed or retimed without touching the transport.

The design notes, the measured figures and the recipes are in ANIMAZIONI.md.
"""

import colorsys
import math
import random
import time

N = 4                   # LED disponibili, indice 0 a sinistra
DESTRA, SINISTRA = +1, -1

NERO = (0, 0, 0)
BIANCO = (255, 255, 255)


# ---------------------------------------------------------------- riproduzione

def riproduci(pad, fotogramma, durata, fps=60, commit=False, gamma_=None):
    """Manda fotogramma(t) al pad per `durata` secondi al ritmo chiesto.

    Le scadenze si calcolano dall'istante iniziale, non sommando pause: un
    `sleep` di durata fissa aggiunge a ogni giro il tempo di trasmissione, e
    a 60 fps nominali se ne ottengono 43 reali. Ancorare ogni fotogramma a
    `inizio + n / fps` fa sì che un giro lento venga riassorbito dal
    successivo invece di slittare per sempre.

    Restituisce (fotogrammi, secondi, saltati); `saltati` conta le scadenze
    già passate all'arrivo, cioè quanto il ritmo chiesto eccede il canale.
    """
    inizio = time.perf_counter()
    n = saltati = 0
    while True:
        t = time.perf_counter() - inizio
        if t >= durata:
            break
        colori = fotogramma(t)
        if gamma_ is not None:
            colori = [gamma(c, gamma_) for c in colori]
        pad.set_indicators(colori, commit=commit)
        n += 1
        scadenza = inizio + n / fps
        ritardo = scadenza - time.perf_counter()
        if ritardo > 0:
            time.sleep(ritardo)
        else:
            saltati += 1
    trascorso = time.perf_counter() - inizio
    return n, trascorso, saltati


def fissa(pad, colori, secondi=0.0, commit=True):
    """Un solo fotogramma, tenuto per il tempo indicato."""
    pad.set_indicators(colori, commit=commit)
    if secondi:
        time.sleep(secondi)


# ------------------------------------------------------------------- il tempo

def fase(t, periodo=1.0):
    """Posizione dentro il ciclo, da 0 a 1, che riparte da capo di scatto."""
    return (t / periodo) % 1.0


def pingpong(x):
    """Piega 0..1 in 0..1..0: andata e ritorno senza salto al giro."""
    x = x % 1.0
    return x * 2 if x < 0.5 else (1 - x) * 2


def battuta(t, bpm):
    """Fase agganciata a un tempo musicale invece che ai secondi."""
    return fase(t, 60.0 / bpm)


# --------------------------------------------------------------- forme d'onda
# Tutte prendono una fase 0..1 e rendono 0..1. Sono il profilo temporale di un
# effetto: decidono *come* una grandezza va da un estremo all'altro.

def seno(x):
    """Salita e discesa morbide, senza spigoli: la piu' naturale all'occhio."""
    return (1 - math.cos(2 * math.pi * x)) / 2


def triangolo(x):
    """Su e giu' a velocita' costante, con due spigoli agli estremi."""
    return pingpong(x)


def dente(x):
    """Sale e ricade di colpo: il profilo di un inseguimento a senso unico."""
    return x % 1.0


def quadra(x, ciclo=0.5):
    """Solo acceso o spento. `ciclo` e' la frazione di tempo acceso."""
    return 1.0 if (x % 1.0) < ciclo else 0.0


def impulso(x, larghezza=0.12, morbido=True):
    """Un lampo breve per giro, il resto buio: eventi, non stati."""
    x = x % 1.0
    if x >= larghezza:
        return 0.0
    return seno(x / larghezza / 2) if morbido else 1.0


def rumore(x, semi=(0.7, 1.3, 2.1)):
    """Tremolio deterministico: seni incommensurabili, mai davvero ripetuto."""
    v = sum(math.sin(2 * math.pi * x * s) for s in semi) / len(semi)
    return (v + 1) / 2


# ----------------------------------------------------------------- transizioni
# Prendono 0..1 e rendono 0..1, ma cambiano il *ritmo* del percorso: dove la
# forma d'onda dice che si va avanti e indietro, l'easing dice se si parte
# piano o si arriva piano.

def lineare(x):
    return x


def dolce(x):
    """Smoothstep: parte e arriva ferma, il compromesso buono per default."""
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def entra(x):
    """Parte piano e accelera: da' peso a quello che arriva."""
    return x * x


def esce(x):
    """Parte veloce e frena: da' peso a quello che se ne va."""
    return 1 - (1 - x) ** 2


def elastico(x):
    """Supera il bersaglio e ci rientra oscillando.

    Unica qui a uscire da 0..1 di proposito: sconfina oltre 1 ed e' quello
    lo scatto che si vede. Chi la usa su una luminosita' deve ritagliarla.
    """
    if x <= 0 or x >= 1:
        return min(1.0, max(0.0, x))
    return 1 + 2 ** (-10 * x) * math.sin((x * 10 - 0.75) * 2 * math.pi / 3)


def rimbalzo(x):
    """Ricade e risale un paio di volte prima di fermarsi."""
    if x < 1 / 2.75:
        return 7.5625 * x * x
    if x < 2 / 2.75:
        x -= 1.5 / 2.75
        return 7.5625 * x * x + 0.75
    if x < 2.5 / 2.75:
        x -= 2.25 / 2.75
        return 7.5625 * x * x + 0.9375
    x -= 2.625 / 2.75
    return 7.5625 * x * x + 0.984375


# -------------------------------------------------------------------- colore

def hsv(h, s=1.0, v=1.0):
    """Tinta, saturazione, luminosita' -> RGB. h gira, quindi 1.1 vale 0.1."""
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, min(1.0, max(0.0, s)),
                                  min(1.0, max(0.0, v)))
    return int(r * 255 + 0.5), int(g * 255 + 0.5), int(b * 255 + 0.5)


def scala(colore, k):
    """Stessa tinta, luminosita' moltiplicata. k=0 spegne."""
    k = max(0.0, k)
    return tuple(min(255, int(c * k + 0.5)) for c in colore)


def mescola(a, b, k):
    """Da `a` (k=0) a `b` (k=1), interpolando ogni canale."""
    k = min(1.0, max(0.0, k))
    return tuple(int(x + (y - x) * k + 0.5) for x, y in zip(a, b))


def somma(a, b):
    """Sovrappone due luci: satura a 255 invece di traboccare."""
    return tuple(min(255, x + y) for x, y in zip(a, b))


def schiarisci(a, b):
    """Tiene il piu' luminoso canale per canale: unisce senza slavare."""
    return tuple(max(x, y) for x, y in zip(a, b))


def moltiplica(a, b):
    """Usa `b` come maschera su `a`: serve per mascherare, non per sommare."""
    return tuple(x * y // 255 for x, y in zip(a, b))


def gamma(colore, g=2.2):
    """Corregge la percezione: senza, meta' luminosita' sembra molto piu'.

    L'occhio non risponde in modo lineare all'energia luminosa. Una rampa
    lineare di byte appare tutta schiacciata sui valori alti, mentre elevare
    a gamma prima di scrivere restituisce una salita che *sembra* uniforme.
    Il device non applica alcuna curva propria: rilegge esattamente i byte
    scritti, quindi la correzione spetta interamente a noi.
    """
    return tuple(int(255 * (c / 255) ** g + 0.5) for c in colore)


def gradiente(fermate, x):
    """Colore a frazione x lungo una lista di fermate equidistanti."""
    if len(fermate) == 1:
        return fermate[0]
    x = min(1.0, max(0.0, x)) * (len(fermate) - 1)
    i = min(int(x), len(fermate) - 2)
    return mescola(fermate[i], fermate[i + 1], x - i)


ARCOBALENO = [hsv(i / 6) for i in range(7)]
FUOCO = [(0, 0, 0), (90, 10, 0), (200, 60, 0), (255, 150, 20), (255, 240, 190)]
GHIACCIO = [(0, 0, 0), (0, 40, 90), (0, 130, 200), (160, 230, 255)]
VU = [(0, 220, 0), (0, 220, 0), (220, 200, 0), (220, 0, 0)]


# --------------------------------------------------------------------- spazio
# Con quattro LED soli la posizione va tenuta come numero reale e distribuita
# fra i vicini: accendere il LED intero piu' vicino fa avanzare il movimento a
# scatti di un quarto, che a queste dimensioni si vede eccome.

def percorso(t, giri_al_secondo=1.0, verso=DESTRA, origine=None, circolare=True):
    """Posizione continua sulla fila, in unita' di LED.

    `verso` decide da che parte si va: DESTRA parte da sinistra e cresce,
    SINISTRA parte da destra e cala.

    `origine` e' l'indice da cui partire ed e' *sempre* nella convenzione
    fisica, 0 a sinistra e 3 a destra, qualunque sia il verso. Lasciandolo a
    None parte dal capo che il verso rende naturale: da 0 andando a destra,
    da 3 andando a sinistra.
    """
    if origine is None:
        origine = 0.0 if verso == DESTRA else N - 1.0
    pos = origine + t * giri_al_secondo * N * verso
    return pos % N if circolare else min(N - 1.0, max(0.0, pos))


def distanza(pos, i, circolare=True):
    """Quanto dista il LED `i` dalla posizione, in unita' di LED.

    Da circolare la fila e' un anello e il LED 3 confina col LED 0: serve
    perche' un inseguimento continuo non abbia un salto al giro. Da lineare
    i due capi sono estremi veri, come vuole un pendolo o un riempimento.
    """
    d = abs(pos - i)
    return min(d, N - d) if circolare else d


def punto(pos, colore=BIANCO, circolare=True):
    """Un punto luminoso alla posizione data, ripartito fra i LED vicini.

    E' l'antialiasing spaziale: a pos 1.25 il LED 1 vale 75% e il 2 vale 25%,
    cosi' il movimento scorre invece di saltare da un LED all'altro.
    """
    fotogramma = [NERO] * N
    base = math.floor(pos)
    frazione = pos - base
    for salto, peso in ((0, 1 - frazione), (1, frazione)):
        if peso <= 0:
            continue
        i = base + salto
        i = i % N if circolare else i
        if 0 <= i < N:
            fotogramma[i] = somma(fotogramma[i], scala(colore, peso))
    return fotogramma


def scia(pos, lunghezza=1.5, verso=DESTRA, circolare=True, forma=None):
    """Intensita' per LED di una coda che segue la testa in `pos`.

    La coda sta *dietro* rispetto al verso di marcia: davanti alla testa
    l'intensita' e' nulla, altrimenti sembra un alone e non un movimento.
    `forma` rimappa il decadimento (default lineare fino a `lunghezza`).
    """
    intensita = []
    for i in range(N):
        # Distanza dietro la testa: positiva alle spalle, negativa davanti.
        # Da circolare la si riporta in [0, N), cosi' la coda rientra dal capo
        # opposto invece di troncarsi quando la testa passa lo zero.
        d = (pos - i) * verso
        if circolare:
            d = d % N
        if d < 0 or d > lunghezza:
            intensita.append(0.0)
            continue
        v = 1 - d / lunghezza
        intensita.append(forma(v) if forma else v)
    return intensita


def barra(livello, parziale=True):
    """Intensita' per LED di un riempimento da sinistra, livello in 0..N."""
    fuori = []
    for i in range(N):
        if livello >= i + 1:
            fuori.append(1.0)
        elif livello <= i:
            fuori.append(0.0)
        else:
            fuori.append(livello - i if parziale else 1.0)
    return fuori


def dipingi(intensita, colore=BIANCO):
    """Da una lista di intensita' a quattro colori della stessa tinta."""
    return [scala(colore, v) for v in intensita]


def colora(intensita, palette):
    """Come dipingi, ma la tinta dipende dalla *posizione* sulla fila."""
    return [scala(gradiente(palette, i / (N - 1)), v)
            for i, v in enumerate(intensita)]


# ----------------------------------------------------------- riordino e strati

def inverti(colori):
    """Specchia la fila: quello che partiva da sinistra parte da destra."""
    return list(colori)[::-1]


def ruota(colori, k):
    """Sposta tutto di k posizioni, riportando in testa quello che esce."""
    k = int(k) % N
    return list(colori[-k:]) + list(colori[:-k]) if k else list(colori)


def specchia(colori):
    """Prende la meta' sinistra e la riflette sulla destra."""
    meta = list(colori[:N // 2])
    return meta + meta[::-1]


def strati(*fotogrammi, fondi=schiarisci):
    """Combina piu' fotogrammi in uno, LED per LED."""
    fuori = [NERO] * N
    for f in fotogrammi:
        fuori = [fondi(a, b) for a, b in zip(fuori, f)]
    return fuori


def dissolvi(a, b, k):
    """Passa dal fotogramma `a` al fotogramma `b`, k da 0 a 1."""
    return [mescola(x, y, k) for x, y in zip(a, b)]


def in_sequenza(*coppie):
    """Concatena effetti: coppie (fotogramma, durata) in un solo fotogramma.

    Utile per un'animazione con un inizio, un centro e una fine — una
    notifica che entra, resta e sfuma — senza scriverne la macchina a stati.
    """
    totale = sum(d for _, d in coppie)

    def fotogramma(t):
        t = t % totale
        for f, d in coppie:
            if t < d:
                return f(t)
            t -= d
        return [NERO] * N
    return fotogramma


def con_decadimento(fotogramma, tenuta=0.85):
    """Aggiunge una coda temporale: ogni LED sfuma invece di spegnersi.

    Serve agli effetti a scatti — scintille, colpi, letture discrete — che
    senza memoria da un fotogramma all'altro risultano duri.
    """
    stato = [NERO] * N

    def avvolto(t):
        nonlocal stato
        stato = [schiarisci(scala(vecchio, tenuta), nuovo)
                 for vecchio, nuovo in zip(stato, fotogramma(t))]
        return stato
    return avvolto


def casuale(probabilita, colore=None):
    """Fotogramma che accende LED a caso: da avvolgere in con_decadimento."""
    def fotogramma(t):
        return [(colore or hsv(random.random()))
                if random.random() < probabilita else NERO for _ in range(N)]
    return fotogramma
