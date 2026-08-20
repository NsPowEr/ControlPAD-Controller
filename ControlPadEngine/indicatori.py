"""I diciassette effetti dei quattro LED indicatori, per l'app.

Le primitive stanno in `effetti.py` e il ragionamento dietro ognuna in
`Come_usare_manipolare_i_4_led/ANIMAZIONI.md`; qui ci sono soltanto gli effetti
finiti, nella forma che serve a chi li sceglie da un menu: parametrizzati sui
quattro colori dell'utente, sulla velocita e sulla luminosita.

Rispetto alla rassegna di `anim.py` cambia una cosa sola, ed e voluta: dove la
versione dimostrativa fissa la tinta nel codice, qui la prende dai quattro
colori scelti. La strada e `fx.colora`, che assegna a ogni LED il *suo* colore
invece di dipingere tutto della stessa tinta — cosi i quattro selettori
dell'app contano davvero anche mentre un effetto gira.

Sei effetti restano coi colori loro (`usa_colori=False`) perche il colore *e*
l'effetto: l'arcobaleno gira l'intera ruota, brace e la palette del fuoco,
vu_meter deve avere l'ultimo LED rosso qualunque sia il livello, polizia sono
blu e rosso in controtempo, countdown verde che diventa allarme, scintille
accende tinte a caso. Prometterne il controllo con un selettore sarebbe
prometterlo a vuoto.

L'animazione gira **qui**, nel motore, non nell'app: il canale regge 250
fotogrammi al secondo e il ritmo va ancorato a scadenze calcolate dall'inizio
(§3.1 di ANIMAZIONI.md), cosa che una `sleep` di durata fissa dal lato Swift
non fa — sommava il tempo di trasmissione a ogni giro e di 30 fps chiesti ne
consegnava 26, con le fasi che divergevano.
"""

import time

import effetti as fx

# Il cursore della velocita e lo stesso dell'illuminazione dei tasti, 0..32,
# perche l'utente non ne impari due. Qui diventa un moltiplicatore del tempo:
# a 0 tutto scorre a poco piu di un terzo, a 32 a due volte e mezzo. Il tetto
# non e tecnico ma percettivo — oltre i tre giri al secondo quattro LED non
# leggono piu un movimento, sfarfallano (§7.2).
VELOCITA_MAX = 32
FATTORE_MIN, FATTORE_MAX = 0.4, 2.4

FPS = 60                 # 6,00 ms per fotogramma: il 24% del canale
CICLO_LENTO = 3.5        # periodo degli effetti che raccontano qualcosa

BIANCHI = [fx.BIANCO] * fx.N


def _tinta(colori, pos):
    """Il colore alla posizione `pos` (0..N-1), interpolando fra i quattro.

    Serve agli effetti che hanno un punto luminoso invece di quattro livelli:
    a pos 1.5 la testa e a meta strada fra il secondo e il terzo colore.
    """
    return fx.gradiente(colori, pos / (fx.N - 1))


# --- movimento ------------------------------------------------------------

def _rincorsa(colori):
    """percorso + scia: la coda dietro la testa dice dove si sta andando."""
    def fotogramma(t):
        pos = fx.percorso(t, giri_al_secondo=1.4)
        return fx.colora(fx.scia(pos, lunghezza=1.6), colori)
    return fotogramma


def _cometa(colori):
    """strati: testa chiara sopra la coda, due livelli sovrapposti."""
    def fotogramma(t):
        pos = fx.percorso(t, giri_al_secondo=1.1)
        coda = fx.colora(fx.scia(pos, lunghezza=2.2, forma=fx.entra), colori)
        return fx.strati(coda, fx.punto(pos, (255, 245, 220)))
    return fotogramma


def _arrivo(colori):
    """verso=SINISTRA: stesso movimento, ma entra da destra."""
    def fotogramma(t):
        pos = fx.percorso(t, giri_al_secondo=1.1, verso=fx.SINISTRA)
        return fx.colora(fx.scia(pos, lunghezza=1.6, verso=fx.SINISTRA), colori)
    return fotogramma


def _pendolo(colori):
    """circolare=False: i capi sono estremi veri, quindi torna indietro."""
    def fotogramma(t):
        pos = fx.seno(fx.fase(t, 1.8)) * (fx.N - 1)
        return fx.punto(pos, _tinta(colori, pos), circolare=False)
    return fotogramma


def _riempimento(colori):
    """barra con riempimento parziale: un livello continuo su quattro passi."""
    def fotogramma(t):
        return fx.colora(fx.barra(fx.pingpong(fx.fase(t, 2.4)) * fx.N), colori)
    return fotogramma


def _onda(colori):
    """sfasamento per indice: la stessa onda letta in quattro punti diversi."""
    def fotogramma(t):
        return [fx.gamma(fx.scala(colori[i], fx.seno(fx.fase(t, 1.1) - i * 0.16)))
                for i in range(fx.N)]
    return fotogramma


# --- colore ---------------------------------------------------------------

def _arcobaleno(_colori):
    """tinta che deriva: h e circolare, quindi puo crescere all'infinito."""
    def fotogramma(t):
        return [fx.hsv(t * 0.35 + i * 0.12) for i in range(fx.N)]
    return fotogramma


def _respiro(colori):
    """seno + gamma: senza la correzione sembrerebbe crollare alla fine."""
    def fotogramma(t):
        v = fx.seno(fx.fase(t, 3.0))
        return [fx.gamma(fx.scala(c, v)) for c in colori]
    return fotogramma


def _battito(colori):
    """due impulsi sfalsati nello stesso giro: il ritmo di un battito."""
    def fotogramma(t):
        v = max(fx.impulso(fx.fase(t, 1.1), 0.16),
                fx.impulso(fx.fase(t, 1.1) - 0.22, 0.16))
        return [fx.gamma(fx.scala(c, v)) for c in colori]
    return fotogramma


def _brace(_colori):
    """rumore sfasato per indice: in fase sembrerebbe un guasto, non fuoco."""
    def fotogramma(t):
        return [fx.gradiente(fx.FUOCO, 0.35 + 0.55 * fx.rumore(t * 0.6 + i * 3.1))
                for i in range(fx.N)]
    return fotogramma


def _scintille(_colori):
    """casuale + con_decadimento: accensioni brusche con una coda temporale."""
    return fx.con_decadimento(fx.casuale(probabilita=0.06), tenuta=0.88)


# --- segnalazione ---------------------------------------------------------

def _allarme(colori):
    """quadra: solo acceso o spento, nessuna sfumatura da interpretare."""
    def fotogramma(t):
        v = fx.quadra(fx.fase(t, 0.22))
        return [fx.scala(c, v) for c in colori]
    return fotogramma


def _polizia(_colori):
    """le due meta in controtempo: stessa onda, una negata rispetto all'altra."""
    def fotogramma(t):
        acceso = fx.quadra(fx.fase(t, 0.34))
        return [fx.hsv(0.62, 1.0, acceso) if i < 2 else fx.hsv(0.0, 1.0, 1 - acceso)
                for i in range(fx.N)]
    return fotogramma


def _notifica(colori):
    """in_sequenza: due lampi, una pausa, poi uno stato di attesa discreto."""
    def lampo(t):
        return [fx.scala(c, fx.impulso(t / 0.18)) for c in colori]

    def attesa(t):
        v = 0.25 * fx.seno(fx.fase(t, 2.0))
        return [fx.scala(c, v) for c in colori]

    return fx.in_sequenza(
        (lampo, 0.18),
        (lambda t: [fx.NERO] * fx.N, 0.10),
        (lampo, 0.18),
        (lambda t: [fx.NERO] * fx.N, 0.25),
        (attesa, 2.0),
    )


def _vu_meter(_colori):
    """colora: la tinta dipende dalla posizione, non dal tempo.

    E quello che serve a un indicatore: l'ultimo LED resta rosso qualunque sia
    il livello, perche e la posizione a portare l'informazione.
    """
    def fotogramma(t):
        livello = fx.N * fx.seno(fx.fase(t, 2.2)) * (0.75 + 0.25 * fx.rumore(t * 4))
        return fx.colora(fx.barra(livello), fx.VU)
    return fotogramma


def _profilo(colori):
    """barra a scalini: qui i quattro LED sono quattro cose distinte.

    Senza riempimento parziale, perche un profilo e intero o non e: un LED a
    meta direbbe qualcosa che non esiste.
    """
    def fotogramma(t):
        attivo = int(fx.fase(t, CICLO_LENTO) * fx.N) + 1
        return fx.colora(fx.barra(attivo, parziale=False), colori)
    return fotogramma


def _countdown(_colori):
    """due fasi in una: lo scalare, e poi il lampeggio d'arrivo.

    La rassegna di `anim.py` lo riproduce una volta sola; qui il tempo va
    ripiegato sul ciclo, perche un effetto scelto da un menu resta in scena
    finche l'utente non ne cambia — senza il modulo, passata la prima volta,
    resterebbe fermo sul lampeggio per sempre.
    """
    def fotogramma(t):
        t = t % CICLO_LENTO
        corsa = t / (CICLO_LENTO * 0.78)
        if corsa < 1.0:
            return fx.dipingi(fx.barra(fx.N * (1 - corsa), parziale=False),
                              fx.hsv(0.28))
        return [fx.hsv(0.0, 1.0, fx.quadra(fx.fase(t, 0.16)))] * fx.N
    return fotogramma


# (id, fabbrica, usa i colori dell'utente). L'ordine e quello del menu
# dell'app: movimento, colore, segnalazione.
CATALOGO = [
    ("rincorsa",    _rincorsa,    True),
    ("cometa",      _cometa,      True),
    ("arrivo",      _arrivo,      True),
    ("pendolo",     _pendolo,     True),
    ("riempimento", _riempimento, True),
    ("onda",        _onda,        True),
    ("arcobaleno",  _arcobaleno,  False),
    ("respiro",     _respiro,     True),
    ("battito",     _battito,     True),
    ("brace",       _brace,       False),
    ("scintille",   _scintille,   False),
    ("allarme",     _allarme,     True),
    ("polizia",     _polizia,     False),
    ("notifica",    _notifica,    True),
    ("vu_meter",    _vu_meter,    False),
    ("profilo",     _profilo,     True),
    ("countdown",   _countdown,   False),
]

FABBRICHE = {nome: fabbrica for nome, fabbrica, _ in CATALOGO}


def elenco():
    """Il catalogo come lo manda il bridge all'app."""
    return [{"id": nome, "uses_colors": usa} for nome, _, usa in CATALOGO]


def fattore_velocita(velocita):
    """Cursore 0..32 -> moltiplicatore del tempo."""
    v = max(0, min(VELOCITA_MAX, int(velocita))) / VELOCITA_MAX
    return FATTORE_MIN + (FATTORE_MAX - FATTORE_MIN) * v


def normalizza(colori):
    """Esattamente quattro terzine, comunque sia fatta la lista in arrivo."""
    fuori = [tuple(c)[:3] for c in (colori or [])][:fx.N]
    while len(fuori) < fx.N:
        fuori.append(fx.BIANCO)
    return fuori


def costruisci(nome, colori=None, velocita=VELOCITA_MAX // 2, luminosita=255):
    """Il fotogramma pronto: effetto scelto, colori dell'utente, tempo scalato
    dalla velocita e tutto ridotto dalla luminosita.

    La luminosita si applica per ultima, come fa il quarto byte del colore nei
    comandi del pad: prima l'effetto decide il suo fotogramma, poi lo si
    abbassa in blocco senza cambiarne le proporzioni.
    """
    if nome not in FABBRICHE:
        raise ValueError(f"effetto indicatori sconosciuto: {nome!r}")

    base = FABBRICHE[nome](normalizza(colori))
    k = fattore_velocita(velocita)
    luce = max(0.0, min(1.0, luminosita / 255))

    def fotogramma(t):
        colori_out = base(t * k)
        if luce >= 1.0:
            return colori_out
        return [fx.scala(c, luce) for c in colori_out]
    return fotogramma


def riproduci_finche(pad, fotogramma, ferma, fps=FPS, commit=False,
                     fra_i_fotogrammi=None, ogni=0.25, banco=None):
    """Come `effetti.riproduci`, ma senza durata: va avanti finche `ferma` —
    un `threading.Event` — non viene alzato.

    Le scadenze restano ancorate all'istante iniziale, che e il punto dell'
    intero meccanismo: un giro lento viene riassorbito dal successivo invece
    di slittare per sempre. L'attesa passa da `ferma.wait()` e non da `sleep`,
    cosi lo stop e immediato e non aspetta la fine del fotogramma in corso.

    `fra_i_fotogrammi` viene chiamata con `pad` ogni `ogni` secondi, fra un
    fotogramma e l'altro. Serve a chi deve parlare col device mentre
    l'animazione va: su macOS il device lo tiene un processo — anzi, un
    handle — solo, e finche questo ciclo gira nessun altro riesce ad aprirlo.
    Chi ha bisogno di chiedere qualcosa al pad passa quindi di qui, sullo
    stesso handle e nello stesso thread, senza contendere niente a nessuno.
    Un'eccezione dalla callback non ferma l'animazione: e ospite, non padrona.

    Restituisce (fotogrammi, secondi, saltati); `saltati` conta le scadenze
    gia passate all'arrivo, cioe di quanto il ritmo chiesto eccede il canale.
    """
    inizio = time.perf_counter()
    n = saltati = 0
    prossima_visita = inizio + ogni
    while not ferma.is_set():
        pad.set_indicators(fotogramma(time.perf_counter() - inizio),
                           commit=commit, banco=banco)
        n += 1

        if fra_i_fotogrammi is not None and time.perf_counter() >= prossima_visita:
            prossima_visita = time.perf_counter() + ogni
            try:
                fra_i_fotogrammi(pad)
            except Exception:
                pass

        ritardo = (inizio + n / fps) - time.perf_counter()
        if ritardo > 0:
            ferma.wait(ritardo)
        else:
            saltati += 1
    return n, time.perf_counter() - inizio, saltati
