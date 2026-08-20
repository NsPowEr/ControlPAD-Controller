#!/usr/bin/env python3
"""Fase 2: verifiche hardware sul dispositivo reale.

Ogni test invia un comando al pad e chiede all'utente di confermare cosa
vede — il device ACKa anche quello che non esegue, quindi l'unica prova
è osservare il risultato fisico.

    python3 test_hardware_fase2.py

Richiede il pad collegato via USB.
"""

import sys
import time

import hid

from controlpad import ControlPad, VID, PID
from session import scrivi, costruisci, FUNZIONI, ROTELLE_DI_FABBRICA
from macro import events_for, TERMINATOR


def _chiedi(domanda):
    """Chiede conferma all'utente. Restituisce True se la risposta è sì."""
    risposta = input(f"\n  → {domanda} [s/n]: ").strip().lower()
    return risposta in ("s", "si", "sì", "y", "yes")


def _sep(titolo):
    print(f"\n{'='*60}")
    print(f"  {titolo}")
    print(f"{'='*60}")


def _ripristina():
    """Rimette il pad nella configurazione pulita: nessuna macro, tutti
    i tasti al default, rotelle di fabbrica."""
    print("\n  Ripristino configurazione pulita...")
    scrivi(verbose=True)
    print("  Fatto.")


# --------------------------------------------------------------------------
# TEST 1: Riassegnazione rotelle (encoder)
# --------------------------------------------------------------------------
def test_rotelle():
    _sep("TEST 1: Riassegnazione rotelle")
    print("""
  Scriverò le rotelle con funzioni diverse da quelle di fabbrica:
    Rotella sinistra → Play/Pausa (antiorario) e Stop (orario)
    Rotella destra   → Traccia prec (antiorario) e Traccia succ (orario)

  Le funzioni di fabbrica sono:
    Sinistra: LED+ / LED−
    Destra:   Volume− / Volume+
""")

    remaps = {
        0xC6: FUNZIONI["play_pausa"],      # sinistra antiorario
        0xC7: FUNZIONI["stop"],             # sinistra orario
        0xF5: FUNZIONI["traccia_prec"],     # destra antiorario
        0xF6: FUNZIONI["traccia_succ"],     # destra orario
    }
    senza_ack = scrivi(remaps=remaps, verbose=True)
    print(f"\n  Scrittura completata ({senza_ack} report senza ACK)")

    ok_sx = _chiedi("Ruota la rotella SINISTRA: fa Play/Pausa e Stop?")
    ok_dx = _chiedi("Ruota la rotella DESTRA: fa Traccia prec/succ?")

    risultato = ok_sx and ok_dx
    print(f"\n  {'✅ PASSATO' if risultato else '❌ FALLITO'}: riassegnazione rotelle")

    # Ripristino
    _ripristina()
    return risultato


# --------------------------------------------------------------------------
# TEST 2: Cambio profilo da software
# --------------------------------------------------------------------------
def test_cambio_profilo():
    _sep("TEST 2: Cambio profilo da software (51 00 00 00 <N>)")
    print("""
  Invierò il comando di cambio profilo direttamente via USB.
  Il pad dovrebbe commutare il banco profilo — osserva se cambia
  qualcosa nei LED o nel comportamento dei tasti.
""")

    path = next((d["path"] for d in hid.enumerate(VID, PID)
                 if d.get("usage_page") == 0xFF00), None)
    if not path:
        print("  ❌ Pad non trovato")
        return False

    dev = hid.device()
    dev.open_path(path)
    risultati = []

    try:
        for profilo in (1, 2, 0):
            cmd = bytes([0x00, 0x51, 0x00, 0x00, 0x00, profilo])
            cmd = cmd.ljust(65, b"\x00")
            dev.write(cmd)
            echo = dev.read(64, timeout_ms=200)
            ack_ok = echo and len(echo) >= 2 and echo[0] == 0x51 and echo[1] == 0x00
            print(f"  Profilo {profilo}: ACK={'sì' if ack_ok else 'no'}, "
                  f"echo={bytes(echo[:4]).hex() if echo else 'nessuno'}")
            time.sleep(0.5)

        ok = _chiedi("Hai visto un cambiamento nel pad al cambio profilo?")
        risultati.append(ok)
    finally:
        dev.close()

    risultato = any(risultati)
    print(f"\n  {'✅ PASSATO' if risultato else '⚠️ INCONCLUSIVO'}: cambio profilo software")
    return risultato


# --------------------------------------------------------------------------
# TEST 3: Stress test capienza macro
# --------------------------------------------------------------------------
def test_stress_macro():
    _sep("TEST 3: Stress test capienza macro")
    print("""
  Scriverò macro di lunghezza crescente su un singolo tasto (n.1, 0x35)
  per trovare il limite fisico massimo di eventi.

  Già verificato fino a 49 eventi. Provo: 60, 80, 100, 120, 150.
""")

    risultati = {}

    for num_eventi in (60, 80, 100, 120, 150):
        # Genera una macro con N pressioni della lettera 'a'
        testo = "a" * (num_eventi // 2)  # 2 eventi per carattere
        eventi = events_for(testo)
        n_reali = (len(eventi) - len(TERMINATOR)) // 4

        print(f"\n  --- {n_reali} eventi ({len(eventi)} byte) ---")

        macros = [(8, 0x35, eventi, "stress")]
        try:
            senza_ack = scrivi(macros=macros, verbose=True)
            print(f"  Scritto: {senza_ack} report senza ACK")

            ok = _chiedi(f"Premi il tasto n.1 (in alto a sinistra): "
                         f"digita {len(testo)} 'a'?")
            risultati[n_reali] = ok

            if not ok:
                print(f"  Limite raggiunto a {n_reali} eventi.")
                break
        except Exception as exc:
            print(f"  ❌ Errore: {exc}")
            risultati[n_reali] = False
            break

    # Ripristino
    _ripristina()

    max_ok = max((n for n, ok in risultati.items() if ok), default=49)
    print(f"\n  Risultato: massimo verificato = {max_ok} eventi")
    for n, ok in sorted(risultati.items()):
        print(f"    {n:4d} eventi: {'✅' if ok else '❌'}")

    return max_ok


# --------------------------------------------------------------------------
# TEST 4: Codici profilo avanti/indietro (esplorativi)
# --------------------------------------------------------------------------
def test_codici_profilo():
    _sep("TEST 4: Codici profilo avanti/indietro (esplorativo)")
    print("""
  Provo i codici candidati per "Profilo +" e "Profilo −" assegnandoli
  a due tasti e verificando se il pad cambia banco.

  Candidati: 0x0111 (profilo +), 0x0112 (profilo −)
  Anche: 0x0180, 0x0183, 0x0184
""")

    candidati = [
        (0x0111, 0x0112, "0x0111/0x0112"),
        (0x0180, 0x0183, "0x0180/0x0183"),
        (0x0184, 0x0185, "0x0184/0x0185"),
    ]

    trovato = None
    for avanti, indietro, desc in candidati:
        print(f"\n  Provo {desc} sui tasti n.1 e n.2...")
        remaps = {0x35: avanti, 0x1E: indietro}
        senza_ack = scrivi(remaps=remaps, verbose=True)

        ok = _chiedi(f"Premi tasto n.1 poi n.2: il profilo cambia avanti/indietro?")
        if ok:
            trovato = desc
            print(f"  ✅ TROVATO: {desc}")
            break
        else:
            print(f"  ❌ {desc} non funziona")

    # Ripristino
    _ripristina()

    if trovato:
        print(f"\n  ✅ Codici profilo avanti/indietro: {trovato}")
    else:
        print(f"\n  ⚠️ Nessun candidato ha funzionato. Serve un'altra cattura da Windows.")

    return trovato


# --------------------------------------------------------------------------
# MAIN
# --------------------------------------------------------------------------
def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║  ControlPad — Fase 2: Verifiche Hardware                    ║
║  Richiede il pad collegato e l'osservazione del dispositivo ║
╚══════════════════════════════════════════════════════════════╝
""")

    # Verifica connessione
    devs = [d for d in hid.enumerate(VID, PID) if d.get("usage_page") == 0xFF00]
    if not devs:
        print("❌ ControlPad non trovato. Collegalo e riprova.")
        sys.exit(1)
    print(f"✅ Pad trovato: {devs[0]['path']}")

    risultati = {}

    if _chiedi("Eseguire TEST 1 (riassegnazione rotelle)?"):
        risultati["rotelle"] = test_rotelle()

    if _chiedi("Eseguire TEST 2 (cambio profilo software)?"):
        risultati["profilo_sw"] = test_cambio_profilo()

    if _chiedi("Eseguire TEST 3 (stress test macro)?"):
        risultati["stress_macro"] = test_stress_macro()

    if _chiedi("Eseguire TEST 4 (codici profilo +/−)?"):
        risultati["profilo_codici"] = test_codici_profilo()

    # Riepilogo
    _sep("RIEPILOGO FASE 2")
    for nome, esito in risultati.items():
        if isinstance(esito, bool):
            print(f"  {nome:20s}: {'✅ PASSATO' if esito else '❌ FALLITO'}")
        elif isinstance(esito, int):
            print(f"  {nome:20s}: max {esito} eventi")
        elif isinstance(esito, str):
            print(f"  {nome:20s}: ✅ {esito}")
        else:
            print(f"  {nome:20s}: ⚠️ {esito}")


if __name__ == "__main__":
    main()
