#!/usr/bin/env python3
"""Cerca sul pad vero i codici di funzione interna che le catture non hanno.

Perche serve
------------
Il campo azione di `51 20` e a 16 bit: sotto 0x0100 e un codice tasto HID, da
0x0100 in su e una funzione del firmware. I codici noti sono quelli che il
software ufficiale ha *scritto* almeno una volta in una cattura — sette in
tutto, piu `0x0110`. "Profilo +" e "Profilo −" non compaiono in nessuna delle
diciannove catture del progetto, comprese quelle registrate apposta per le
funzioni interne: non e che manchi la decodifica, e che quei byte non sono
mai passati sul cavo. Inventarseli non e un'opzione, quindi si chiedono al
device.

Come
----
Due fasi, che rispondono a due domande diverse.

**Mappa** (`--mappa`) — la modalita che serve. Assegna ventiquattro candidati
ai ventiquattro tasti in una sola scrittura, poi sta in ascolto mentre li si
preme tutti. Non serve dire quale tasto si sta premendo: lo dice il pad.

    52 00 00 00 <banco>            il banco di profilo e cambiato
    52 28 00 00 <slot>             la modalita di illuminazione e cambiata
    43 01 00 00 <indice> c0 | 40   tasto premuto (c0) o rilasciato (40)

L'`<indice>` e quello per colonne di `layout.indice_colonne`, lo stesso della
tabella `51 94` — verificato sulla cattura: il tasto `x` (HID `0x1b`, riga 4
colonna 3) si annuncia come `0x0d`, che e `2*5+3`. Da li si risale al tasto,
quindi al candidato che gli era stato assegnato. Un `52 00` che arriva subito
dopo una pressione e attribuito a quel candidato: quello e "profilo ±", e il
verso lo dice il banco rispetto al precedente.

**Setaccio** (`--setaccio`) — scrive i candidati e li rilegge con
`52 20 <tasto> 00` per vedere quali il firmware conserva. *Esito negativo,
misurato*: sul PID 0x0130 il firmware conserva qualunque valore a 16 bit, e
0x0100..0x012f si rileggono tutti identici, compresi quelli che non
significano niente. La rilettura dice cosa c'e scritto, non cosa viene
eseguito, quindi da sola non identifica un codice valido. Resta utile per
verificare che una scrittura sia arrivata; non usarla per scoprire funzioni.

Uso
---
    python3 sonda_funzioni.py --sorveglia 60          # il controllo giusto su macOS
    python3 sonda_funzioni.py --ascolta 30            # solo report spontanei
    python3 sonda_funzioni.py --mappa --da 0x0100 --a 0x0117
    python3 sonda_funzioni.py --prova 0x0111 0x0112     # uno per volta
    python3 sonda_funzioni.py --setaccio --da 0x0100 --a 0x0117

Alla fine rimette sempre il pad in configurazione pulita.
"""

import argparse
import sys
import time

import hid

from controlpad import ControlPad, VID, PID, attendi_ack
import effects
from layout import NOMI, indice_colonne, posizione, tasto_da_indice_colonne, tutti_i_tasti
from session import FUNZIONI, scrivi

# I codici gia visti in cattura: il setaccio li usa come controllo. Se il
# device li rifiutasse, a essere rotto sarebbe il setaccio, non i candidati.
NOTI = {v: k for k, v in FUNZIONI.items()}

TASTI = tutti_i_tasti()


def _nome(codice):
    return NOMI.get(codice, f"0x{codice:02x}")


def _leggi_keymap(pad, tasti):
    """{codice_tasto: azione} riletta dal device con 52 20.

    E una lettura dal vivo, fuori da qualunque sessione: e cosi che il
    software ufficiale ricarica la configurazione all'avvio, e si vede nelle
    catture subito prima di ogni scrittura.
    """
    letto = {}
    for tasto in tasti:
        risposta = pad._send(bytes([0x52, 0x20, tasto, 0x00]), f"leggi {tasto:02x}")
        if risposta is None or len(risposta) < 6:
            letto[tasto] = None
            continue
        letto[tasto] = risposta[4] | (risposta[5] << 8)
    return letto


def _ascolta(dev, secondi, su_evento):
    """Legge i report non richiesti per un po', drenando la coda a ogni giro.

    Stesso ritmo del bridge: e il timeout della `read` a fare da attesa, mai
    uno sleep — un pacchetto che arriva deve essere visto subito, e le
    pressioni di tasto ne generano parecchi.
    """
    scadenza = time.monotonic() + secondi
    while time.monotonic() < scadenza:
        try:
            dati = dev.read(64, timeout_ms=50)
        except Exception as exc:
            print(f"    !! lettura interrotta: {exc}")
            return
        if not dati:
            continue
        rep = bytes(dati)
        if rep[:1] == b"\x00":
            rep = rep[1:]
        if len(rep) < 6:
            continue
        su_evento(rep)


def _descrivi(rep):
    """Cosa dice un report non richiesto, in una riga."""
    testa = rep[:4]
    if testa == b"\x52\x00\x00\x00":
        return f"banco di profilo -> {rep[4]}"
    if testa == b"\x52\x28\x00\x00":
        return f"modalita di illuminazione -> {rep[4]}"
    if testa == b"\x43\x01\x00\x00":
        verso = {0xC0: "premuto", 0x40: "rilasciato"}.get(rep[5])
        if verso:
            return f"tasto indice {rep[4]} {verso}"
    return None


# --------------------------------------------------------------------------
# Fase 1: setaccio
# --------------------------------------------------------------------------
def setaccio(da, a):
    """Scrive i candidati a blocchi di ventiquattro e li rilegge."""
    candidati = list(range(da, a + 1))
    print(f"Setaccio di {len(candidati)} candidati, da 0x{da:04x} a 0x{a:04x}.")
    print(f"Servono {(len(candidati) + len(TASTI) - 1) // len(TASTI)} "
          "scritture di sessione.\n")

    accettati, rifiutati = {}, {}

    for inizio in range(0, len(candidati), len(TASTI)):
        blocco = candidati[inizio:inizio + len(TASTI)]
        remaps = dict(zip(TASTI, blocco))

        senza_ack = scrivi(remaps=remaps)
        if senza_ack:
            print(f"  !! {senza_ack} report senza ACK: il blocco "
                  f"0x{blocco[0]:04x}.. non e attendibile")

        time.sleep(0.3)
        with ControlPad() as pad:
            letto = _leggi_keymap(pad, list(remaps))

        for tasto, atteso in remaps.items():
            trovato = letto.get(tasto)
            etichetta = f" ({NOTI[atteso]})" if atteso in NOTI else ""
            if trovato == atteso:
                accettati[atteso] = trovato
                print(f"  0x{atteso:04x} accettato{etichetta}")
            else:
                rifiutati[atteso] = trovato
                mostra = "nessuna risposta" if trovato is None else f"0x{trovato:04x}"
                print(f"  0x{atteso:04x} rifiutato -> {mostra}{etichetta}")

    print("\n" + "=" * 62)
    print(f"Accettati: {len(accettati)}  ·  rifiutati: {len(rifiutati)}")
    ignoti = [c for c in sorted(accettati) if c not in NOTI]
    if ignoti:
        print("\nAccettati e non ancora in tabella — da provare con --prova:")
        print("  " + " ".join(f"0x{c:04x}" for c in ignoti))
    else:
        print("\nNessun codice accettato oltre a quelli gia noti.")

    controllo = [c for c in NOTI if da <= c <= a]
    if controllo:
        falliti = [c for c in controllo if c not in accettati]
        if falliti:
            print("\n!! I codici gia visti in cattura " +
                  " ".join(f"0x{c:04x}" for c in falliti) +
                  " risultano rifiutati: e il setaccio a non funzionare, non "
                  "i candidati. Non fidarsi del resto di questo elenco.")
        else:
            print(f"\nControllo: i {len(controllo)} codici gia noti in questo "
                  "intervallo sono stati accettati, quindi il metodo regge.")

    return accettati


# --------------------------------------------------------------------------
# Fase 2: prova sul campo
# --------------------------------------------------------------------------
def prova(codici, tasto=0x35, attesa=12.0):
    """Assegna un candidato a un tasto e guarda cosa fa il pad quando lo premi."""
    print(f"Prova sul tasto '{_nome(tasto)}'.\n")

    for codice in codici:
        etichetta = f" ({NOTI[codice]})" if codice in NOTI else ""
        print("=" * 62)
        print(f"  0x{codice:04x}{etichetta}")
        print("=" * 62)

        senza_ack = scrivi(remaps={tasto: codice})
        if senza_ack:
            print(f"  !! {senza_ack} report senza ACK")
        time.sleep(0.3)

        path = next((d["path"] for d in hid.enumerate(VID, PID)
                     if d.get("usage_page") == 0xFF00), None)
        if path is None:
            print("  !! pad non trovato")
            return
        dev = hid.device()
        dev.open_path(path)
        dev.set_nonblocking(0)
        try:
            # Si legge il banco di partenza: e il numero con cui confrontare.
            dev.write(bytes([0x00]) + bytes([0x52, 0x00, 0x00, 0x00]).ljust(64, b"\x00"))
            banco_prima = None
            def primo(rep):
                nonlocal banco_prima
                if rep[:4] == b"\x52\x00\x00\x00" and banco_prima is None:
                    banco_prima = rep[4]
            _ascolta(dev, 0.5, primo)
            print(f"  banco di partenza: {banco_prima}")

            print(f"\n  → premi ora il tasto '{_nome(tasto)}', "
                  f"{attesa:.0f} secondi di ascolto...\n")
            visti = []
            _ascolta(dev, attesa, lambda rep: visti.append(rep))
        finally:
            dev.close()

        righe = [d for d in (_descrivi(r) for r in visti) if d]
        premuto = any("premuto" in r for r in righe)
        banchi = [r for r in righe if "banco" in r]
        modalita = [r for r in righe if "modalita" in r]

        for riga in righe:
            print(f"    {riga}")
        if not righe:
            print("    (niente)")

        print()
        if not premuto:
            print("  ESITO: il tasto non ha annunciato niente — premuto davvero?")
        elif banchi:
            print(f"  ESITO: 0x{codice:04x} CAMBIA BANCO DI PROFILO. {banchi[-1]}")
            print("         Il verso lo dice il numero rispetto a "
                  f"{banco_prima}: cresce = profilo +, cala = profilo −.")
        elif modalita:
            print(f"  ESITO: 0x{codice:04x} cambia modalita di illuminazione.")
        else:
            print(f"  ESITO: 0x{codice:04x} accettato ma senza effetto "
                  "osservabile da qui (potrebbe agire su luminosita o "
                  "velocita, che il pad non annuncia).")
        print()


# --------------------------------------------------------------------------
# Fase 2 bis: ventiquattro candidati in un colpo solo
# --------------------------------------------------------------------------
def mappa(candidati, ascolto=120.0):
    """Assegna un candidato per tasto e sta a guardare cosa fa premerli.

    Una scrittura sola invece di una per candidato: il blob va in flash, e
    ventiquattro riscritture per sfogliare ventiquattro codici sono
    ventiquattro volte l'usura e venti minuti di attesa. Chi preme non deve
    tenere il conto di dove si trova, perche ogni pressione si annuncia col
    suo indice.
    """
    candidati = candidati[:len(TASTI)]
    assegnati = dict(zip(TASTI, candidati))

    print(f"Scrittura di {len(assegnati)} candidati, uno per tasto.\n")
    senza_ack = scrivi(remaps=assegnati)
    if senza_ack:
        print(f"  !! {senza_ack} report senza ACK: la scrittura non e attendibile\n")
    time.sleep(0.4)

    print("  tasto        posizione   candidato")
    print("  " + "-" * 38)
    for tasto, codice in assegnati.items():
        riga, colonna = posizione(tasto)
        etichetta = f"  ({NOTI[codice]})" if codice in NOTI else ""
        print(f"  {_nome(tasto):<12} r{riga} c{colonna}      "
              f"0x{codice:04x}{etichetta}")

    path = next((d["path"] for d in hid.enumerate(VID, PID)
                 if d.get("usage_page") == 0xFF00), None)
    if path is None:
        print("\n  !! pad non trovato")
        return {}
    dev = hid.device()
    dev.open_path(path)
    dev.set_nonblocking(0)

    esiti = {}
    premuti = {}                        # {codice tasto: quante volte}
    ultima_pressione = [None, 0.0]      # (codice tasto, istante)
    banco = [None]

    def su_report(rep):
        testa = rep[:4]
        adesso = time.monotonic()

        if testa == b"\x43\x01\x00\x00" and rep[5] == 0xC0:
            try:
                tasto = tasto_da_indice_colonne(rep[4])
            except KeyError:
                tasto = None
            ultima_pressione[0] = tasto
            ultima_pressione[1] = adesso
            if tasto is not None:
                premuti[tasto] = premuti.get(tasto, 0) + 1
                if premuti[tasto] == 1:
                    # Riscontro immediato: chi preme deve vedere che la sonda
                    # lo sente, altrimenti un cavo staccato o un'interfaccia
                    # sbagliata si scoprono solo a fine prova.
                    print(f"    premuto '{_nome(tasto)}' "
                          f"= 0x{assegnati[tasto]:04x}   "
                          f"({len(premuti)}/{len(assegnati)} tasti)")
            return

        if testa == b"\x52\x00\x00\x00":
            prima, banco[0] = banco[0], rep[4]
            if prima is None or prima == rep[4]:
                return
            descrizione = f"banco {prima} -> {rep[4]}"
        elif testa == b"\x52\x28\x00\x00":
            descrizione = f"modalita di illuminazione -> {rep[4]}"
        else:
            return

        tasto = ultima_pressione[0]
        # Mezzo secondo: il pad annuncia l'effetto subito dopo la pressione,
        # e piu in la sarebbe un altro tasto o un tocco di rotella.
        if tasto is None or adesso - ultima_pressione[1] > 0.5:
            print(f"    {descrizione}  (nessuna pressione recente a cui "
                  "attribuirlo)")
            return
        codice = assegnati[tasto]
        esiti.setdefault(codice, []).append(descrizione)
        print(f"    tasto '{_nome(tasto)}' = 0x{codice:04x}  ->  {descrizione}")

    try:
        # Il banco di partenza, per avere il numero con cui confrontare.
        dev.write(bytes([0x00]) + bytes([0x52, 0x00, 0x00, 0x00]).ljust(64, b"\x00"))
        _ascolta(dev, 0.6, lambda rep: banco.__setitem__(
            0, rep[4]) if rep[:4] == b"\x52\x00\x00\x00" else None)
        print(f"\n  banco di partenza: {banco[0]}")
        print(f"\n  → premi ora i ventiquattro tasti, uno alla volta, con un "
              f"secondo di pausa.\n    {ascolto:.0f} secondi di ascolto.\n")
        _ascolta(dev, ascolto, su_report)
    finally:
        dev.close()

    print("\n" + "=" * 62)

    if not premuti:
        print("PROVA NON VALIDA: nessuna pressione ricevuta in tutto l'ascolto.")
        print("Il pad non ha mandato un solo report 43 01, quindi non si puo")
        print("dire niente sui candidati: 'nessun effetto' e 'nessuno ha")
        print("premuto' da qui sono indistinguibili. Rilancia con il pad a")
        print("portata di mano e premi i tasti mentre l'ascolto e aperto.")
        return {}

    mancanti = [t for t in assegnati if t not in premuti]
    if mancanti:
        print(f"Attenzione: {len(mancanti)} tasti non sono mai stati premuti "
              f"({', '.join(_nome(t) for t in mancanti)}).")
        print("Sui loro candidati questa prova non dice niente.\n")

    profilo = {c: v for c, v in esiti.items() if any("banco" in x for x in v)}
    if profilo:
        print("CODICI CHE CAMBIANO BANCO DI PROFILO:")
        for codice, effetti in sorted(profilo.items()):
            print(f"  0x{codice:04x}  " + " · ".join(effetti))
    else:
        print("Nessuno dei candidati ha cambiato banco di profilo.")
    altri = {c: v for c, v in esiti.items() if c not in profilo}
    if altri:
        print("\nAltri effetti osservati:")
        for codice, effetti in sorted(altri.items()):
            print(f"  0x{codice:04x}  " + " · ".join(effetti))
    muti = [assegnati[t] for t in premuti if assegnati[t] not in esiti]
    if muti:
        print("\nPremuti ma senza effetto osservabile: " +
              " ".join(f"0x{c:04x}" for c in sorted(muti)))
        print("(la luminosita e la velocita il pad non le annuncia, quindi un "
              "codice puo agire senza comparire qui)")
    return esiti


# --------------------------------------------------------------------------
# Modalita di controllo: solo ascolto, nessuna scrittura
# --------------------------------------------------------------------------
def ascolta_e_basta(secondi=30.0):
    """Stampa quello che il pad dice, senza toccargli niente.

    Serve prima di --mappa: se qui non compare una riga a ogni pressione, la
    prova mappata non puo dire niente, e la colpa non e dei candidati. Non
    scrive in flash, quindi si puo lanciare quante volte si vuole.
    """
    path = next((d["path"] for d in hid.enumerate(VID, PID)
                 if d.get("usage_page") == 0xFF00), None)
    if path is None:
        print("Pad non trovato.")
        return
    dev = hid.device()
    dev.open_path(path)
    dev.set_nonblocking(0)
    print(f"Ascolto per {secondi:.0f} secondi. Premi i tasti del pad, gira le "
          "rotelle, cambia banco.\n")
    conteggio = [0]

    def mostra(rep):
        descrizione = _descrivi(rep)
        if descrizione is None:
            return
        conteggio[0] += 1
        print(f"  {descrizione}")

    try:
        _ascolta(dev, secondi, mostra)
    finally:
        dev.close()

    print()
    if conteggio[0]:
        print(f"{conteggio[0]} eventi ricevuti: il canale funziona, "
              "--mappa puo dare un esito valido.")
    else:
        print("Nessun evento. O non e stato premuto niente, o il pad manda i "
              "suoi report altrove: in questo stato --mappa non conclude nulla.")


# --------------------------------------------------------------------------
# Sorveglianza: lo stato del pad chiesto di continuo
# --------------------------------------------------------------------------
def sorveglia(secondi=60.0, intervallo=0.25):
    """Mostra banco e modalita finche non si smette, interrogando il pad.

    E il controllo giusto su macOS. `--ascolta` aspetta i report spontanei,
    che qui non arrivano mai: stampa zero anche quando tutto funziona, e non
    dice niente. Questo invece chiede, come fa il motore, quindi quello che si
    vede qui e esattamente quello che l'app puo sapere.

    Non scrive in flash. Non si puo pero usare mentre l'app e aperta: su macOS
    il device lo tiene un processo solo, e il secondo `open_path` fallisce.
    """
    path = next((d["path"] for d in hid.enumerate(VID, PID)
                 if d.get("usage_page") == 0xFF00), None)
    if path is None:
        print("Pad non trovato.")
        return
    try:
        dev = hid.device()
        dev.open_path(path)
        dev.set_nonblocking(0)
    except Exception as exc:
        print(f"Device occupato ({exc}). Chiudi ControlPad.app e riprova: su "
              "macOS il pad lo tiene un processo solo.")
        return

    def chiedi(comando):
        pl = bytes(comando).ljust(64, b"\x00")
        dev.write(b"\x00" + pl)
        risposta = attendi_ack(dev, pl[:2], timeout_ms=200)
        return risposta[4] if risposta else None

    print(f"Sorveglianza per {secondi:.0f} s, una lettura ogni "
          f"{intervallo*1000:.0f} ms.")
    print("Premi i tasti del pad: ogni cambiamento compare qui.\n")

    banco = modalita = None
    cambi = 0
    scadenza = time.monotonic() + secondi
    try:
        while time.monotonic() < scadenza:
            b, m = chiedi([0x52, 0x00, 0x00, 0x00]), chiedi([0x52, 0x28, 0x00, 0x00])
            trascorso = secondi - (scadenza - time.monotonic())
            if b is not None and b != banco:
                if banco is not None:
                    cambi += 1
                    print(f"  {trascorso:6.1f}s  BANCO      {banco} -> {b}")
                else:
                    print(f"  {trascorso:6.1f}s  banco di partenza: {b}")
                banco = b
            if m is not None and m != modalita:
                if modalita is not None:
                    cambi += 1
                    nome = (effects.SLOT_ORDER[m]
                            if m < len(effects.SLOT_ORDER) else "?")
                    print(f"  {trascorso:6.1f}s  MODALITA   {modalita} -> {m}  ({nome})")
                else:
                    print(f"  {trascorso:6.1f}s  modalita di partenza: {m}")
                modalita = m
            time.sleep(intervallo)
    except KeyboardInterrupt:
        pass
    finally:
        dev.close()

    print(f"\n{cambi} cambiamenti in {secondi:.0f} s.")
    if not cambi:
        print("Il pad non ha cambiato ne banco ne modalita. Se hai premuto i "
              "tasti,\nvuol dire che a quei tasti non e assegnata nessuna "
              "funzione che cambi\nlo stato — non che la lettura sia rotta.")
    else:
        print("La lettura funziona: questi stessi cambiamenti l'app li riceve "
              "come\neventi hardware_profile_changed / hardware_mode_changed.")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sorveglia", nargs="?", type=float, const=60.0,
                   metavar="SECONDI",
                   help="mostra banco e modalita interrogando il pad (il controllo giusto su macOS)")
    p.add_argument("--ascolta", nargs="?", type=float, const=30.0,
                   metavar="SECONDI",
                   help="stampa e basta quello che dice il pad, senza scrivere niente")
    p.add_argument("--mappa", action="store_true",
                   help="assegna un candidato per tasto e guarda cosa fa premerli")
    p.add_argument("--setaccio", action="store_true",
                   help="scrive e rilegge i candidati (esito negativo: vedi il docstring)")
    p.add_argument("--da", type=lambda s: int(s, 0), default=0x0100)
    p.add_argument("--a", type=lambda s: int(s, 0), default=0x0117)
    p.add_argument("--ascolto", type=float, default=120.0,
                   help="secondi di ascolto in modalita --mappa")
    p.add_argument("--prova", nargs="+", type=lambda s: int(s, 0), metavar="CODICE",
                   help="assegna ogni codice a un tasto e guarda cosa fa premendolo")
    p.add_argument("--tasto", type=lambda s: int(s, 0), default=0x35,
                   help="codice HID del tasto da usare per --prova (default 0x35, il n.1)")
    args = p.parse_args()

    if not any(d.get("usage_page") == 0xFF00 for d in hid.enumerate(VID, PID)):
        print("Pad non collegato.")
        return 1
    if not any((args.setaccio, args.prova, args.mappa, args.ascolta,
                args.sorveglia)):
        p.print_help()
        return 1

    if args.sorveglia:
        sorveglia(args.sorveglia)          # non scrive niente
        return 0

    if args.ascolta:
        # Non scrive niente, quindi non c'e niente da ripristinare.
        ascolta_e_basta(args.ascolta)
        return 0

    try:
        if args.mappa:
            mappa(list(range(args.da, args.a + 1)), ascolto=args.ascolto)
        if args.setaccio:
            setaccio(args.da, args.a)
        if args.prova:
            prova(args.prova, tasto=args.tasto)
    finally:
        print("\nRipristino della configurazione pulita...")
        scrivi()
        print("Fatto.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
