"""Server JSON-lines per il ControlPad, pensato per essere lanciato come
sottoprocesso da un'app Swift.

Protocollo: una riga JSON per comando su stdin, una riga JSON di risposta su
stdout, flush immediato. Ogni richiesta porta un "id" che torna identico nella
risposta. Il processo emette inoltre righe non richieste (senza "id") per
segnalare cambi di stato della connessione:

    -> {"id": 1, "cmd": "set_static", "r": 255, "g": 0, "b": 0}
    <- {"id": 1, "ok": true}

    <- {"event": "connection", "present": false}

Non riscrive alcuna parte del protocollo USB: ogni comando richiama
direttamente le funzioni già verificate in controlpad.py / session.py /
macro.py. Questo file è solo la busta JSON attorno a quelle funzioni.
"""

import json
import os
import signal
import sys
import threading
import time
import traceback

import hid

import effects
import indicatori
from controlpad import ControlPad, VID, PID
from macro import events_for, events_for_combo, EventList
from session import scrivi as session_scrivi

POLL_INTERVAL = 2.0

LOG = os.path.expanduser("~/Library/Logs/ControlPad-engine.log")


def _log(testo):
    """Diario del motore.

    L'app Swift butta lo stderr del sottoprocesso in /dev/null, quindi finora
    un errore qui dentro spariva senza lasciare traccia: si vedeva solo che
    "non funziona niente". Ogni comando e ogni eccezione finiscono in un file,
    che è la prima cosa da guardare quando qualcosa non risponde.
    """
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%H:%M:%S')} {testo}\n")
    except Exception:
        pass                                   # il log non deve mai far cadere il motore


def _device_present():
    return any(d.get("usage_page") == 0xFF00 for d in hid.enumerate(VID, PID))


def _reply(id_, **fields):
    line = json.dumps({"id": id_, **fields}, separators=(",", ":"))
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def _event(**fields):
    line = json.dumps(fields, separators=(",", ":"))
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


_pad_aperto = None


def _pad_persistente():
    """Un ControlPad già aperto, riusato fra un comando e il successivo.

    Serve a chi manda fotogrammi uno per uno da fuori (`set_indicators` con
    `stream`): aprire e chiudere il device a ogni fotogramma costa molto più
    dell'invio stesso. Gli effetti dell'app non passano più da qui — li
    disegna `_avvia_animazione` con un handle suo — ma il comando resta, ed è
    la strada per un'animazione pilotata dall'esterno.
    """
    global _pad_aperto
    if _pad_aperto is None:
        _pad_aperto = ControlPad().__enter__()
    return _pad_aperto


def _chiudi_pad_persistente():
    """Il device va lasciato libero prima di una scrittura di sessione, che
    apre la sua connessione: due handle aperti insieme sullo stesso device non
    sono garantiti."""
    global _pad_aperto
    if _pad_aperto is not None:
        try:
            _pad_aperto.__exit__(None, None, None)
        finally:
            _pad_aperto = None


_animazione = None          # il thread che disegna i LED indicatori
_stop_animazione = None     # l'evento con cui gli si chiede di smettere

# I quattro colori fissi dell'utente, ricordati per poterli rimettere quando
# l'animazione finisce — compreso il caso in cui finisce perché il motore sta
# morendo. Il registro degli indicatori sopravvive allo scollegamento: senza
# questo ripristino il pad si riaccende sull'ultimo fotogramma in cui l'ha colto
# la chiusura del programma, che è la cosa che l'utente vede come "i colori
# fissi sono stati dimenticati".
_colori_fissi = None


def _ripristina_fissi():
    """Rimette i colori fissi, se il pad c'è e se ne conosciamo.

    Chiamata sia dall'uscita normale (stdin chiuso: l'app è stata chiusa) sia
    dal gestore di SIGTERM, che è come `Process.terminate()` di Swift chiude il
    motore — senza gestore Python uscirebbe subito, prima di riscrivere niente.
    """
    _ferma_animazione()
    if not _colori_fissi or not _device_present():
        return
    try:
        with ControlPad() as pad:
            pad.set_indicators(_colori_fissi, commit=True)
        _log(f"   indicatori riportati ai fissi {_colori_fissi}")
    except Exception as exc:
        _log(f"!! ripristino indicatori fallito: {exc}")


def _ferma_animazione():
    """Ferma l'effetto in corso sui LED indicatori e aspetta il suo thread.

    Aspettarlo non è pignoleria: il thread tiene aperto il device per conto
    proprio, e ogni altro comando ne apre uno a sua volta. Due handle insieme
    sullo stesso device non sono garantiti, quindi si va in fila.
    """
    global _animazione, _stop_animazione
    if _animazione is None:
        return
    _stop_animazione.set()
    _animazione.join(timeout=2.0)
    _animazione = _stop_animazione = None


def _avvia_animazione(fotogramma):
    """Un thread che manda fotogrammi finché non gli si dice di smettere.

    L'animazione vive nel motore e non nell'app perché il ritmo va tenuto con
    scadenze ancorate all'istante iniziale: dal lato Swift ogni giro sommava i
    6 ms di trasmissione alla pausa, consegnando 26 fps dei 30 chiesti e
    facendo divergere le fasi. Vedi indicatori.riproduci_finche.
    """
    global _animazione, _stop_animazione
    _ferma_animazione()
    _stop_animazione = threading.Event()

    def corri(ferma=_stop_animazione):
        try:
            with ControlPad() as pad:
                n, sec, saltati = indicatori.riproduci_finche(pad, fotogramma, ferma)
            _log(f"   animazione chiusa: {n} fotogrammi in {sec:.1f}s, "
                 f"{saltati} oltre il ritmo")
        except Exception as exc:
            # Pad staccato a metà animazione: il thread muore qui e basta, il
            # comando successivo riapre. Senza questo log spariva in silenzio.
            _log(f"!! animazione indicatori interrotta: {exc}")

    _animazione = threading.Thread(target=corri, daemon=True, name="indicatori")
    _animazione.start()


def _grid_from_json(colors):
    """{"c,r": [r,g,b]} -> {(c, r): (r, g, b)}, chiavi come le manda Swift."""
    out = {}
    for key, rgb in colors.items():
        c, r = (int(x) for x in key.split(","))
        out[(c, r)] = tuple(rgb)
    return out


def _eventi_da_macro(m):
    """Una voce macro dal client: testo semplice, combinazione di tasti, o
    eventi grezzi (pressione/rilascio con ritardo esplicito, come li registra
    l'app ufficiale premendo i tasti a mano)."""
    if m["kind"] == "text":
        return events_for(m["text"])
    if m["kind"] == "combo":
        return events_for_combo(m["usages"])
    if m["kind"] == "raw":
        ev = EventList()
        for step in m["events"]:
            if step["press"]:
                ev.press(step["usage"], step["delay"])
            else:
                ev.release(step["usage"], step["delay"])
        return ev.done()
    raise ValueError(f"tipo macro sconosciuto: {m['kind']!r}")


def handle(req):
    global _colori_fissi

    cmd = req["cmd"]

    # Ogni comando che apre il device per conto suo pretende che l'animazione
    # dei LED indicatori sia ferma e l'handle tenuto aperto sia chiuso prima.
    SOLA_LETTURA = ("ping", "status", "list_modes", "list_indicator_effects")

    if cmd not in SOLA_LETTURA:
        _ferma_animazione()
    if cmd not in SOLA_LETTURA + ("set_indicators",):
        _chiudi_pad_persistente()

    if cmd == "ping":
        return {"pong": True}

    if cmd == "status":
        return {"present": _device_present()}

    if cmd == "set_static":
        with ControlPad() as pad:
            pad.set_static(req["r"], req["g"], req["b"],
                            req.get("brightness", 0xFF))
        return {}

    if cmd == "set_effect":
        with ControlPad() as pad:
            pad.set_effect(req["effect"], req.get("r", 0xFF), req.get("g", 0xFF),
                            req.get("b", 0xFF), speed=req.get("speed", 0),
                            brightness=req.get("brightness", 0xFF))
        return {}

    if cmd == "list_modes":
        return {"modes": effects.describe()}

    if cmd == "set_mode":
        with ControlPad() as pad:
            pad.set_mode(req["mode"],
                          color1=req.get("color1"), color2=req.get("color2"),
                          speed=req.get("speed"))
        return {}

    if cmd == "set_grid":
        with ControlPad() as pad:
            pad.set_grid(_grid_from_json(req["colors"]))
        return {}

    if cmd == "set_indicators":
        colors = [tuple(c) for c in req["colors"]]
        if not req.get("stream"):
            _colori_fissi = colors      # un colore fisso è per definizione quello
        # Solo i fotogrammi di un'animazione tengono aperto il device: un
        # colore fisso è un colpo solo, e lasciare l'handle aperto per sempre
        # dopo di esso impedirebbe a chiunque altro di parlare col pad.
        if not req.get("stream"):
            _chiudi_pad_persistente()
            with ControlPad() as pad:
                pad.set_indicators(colors, commit=True)
            return {}
        try:
            _pad_persistente().set_indicators(colors)
        except Exception:
            # Pad staccato a metà animazione: si butta l'handle e si rilancia,
            # così il tentativo successivo riapre invece di insistere su uno
            # descrittore morto.
            _chiudi_pad_persistente()
            raise
        return {}

    if cmd == "list_indicator_effects":
        return {"effects": indicatori.elenco()}

    if cmd == "start_indicator_effect":
        # I colori fissi viaggiano insieme all'effetto: sono quelli a cui
        # tornare quando l'animazione finisce, e vanno saputi *prima*, perché
        # uno dei modi in cui finisce è che il motore venga chiuso.
        _colori_fissi = [tuple(c) for c in req.get("static", [])] or _colori_fissi

        # Un comando solo per tutta l'animazione: il motore la disegna finché
        # non gli si dice di smettere. L'app non manda più un fotogramma per
        # volta, quindi il ritmo non dipende più dalla latenza del bridge.
        _avvia_animazione(indicatori.costruisci(
            req["effect"],
            colori=[tuple(c) for c in req.get("colors", [])],
            velocita=req.get("speed", indicatori.VELOCITA_MAX // 2),
            luminosita=req.get("brightness", 255)))
        return {}

    if cmd == "stop_indicator_effect":
        # L'animazione l'ha già fermata il preambolo di handle(); qui si
        # rimettono i colori fissi, altrimenti i LED resterebbero fermi sul
        # fotogramma a metà ciclo in cui li ha colti lo stop.
        # Col pad staccato non c'e niente da rimettere: fermare l'animazione è
        # comunque riuscito, e far fallire lo stop trasformerebbe uno scollega-
        # mento in un errore rosso nell'app.
        colors = [tuple(c) for c in req.get("colors", [])]
        if colors:
            _colori_fissi = colors
        if colors and _device_present():
            with ControlPad() as pad:
                pad.set_indicators(colors, commit=True)
        return {}

    if cmd == "read_indicators":
        # Rilettura dell'indirizzo 0x00fc: dice cosa il device *ha* davvero,
        # che è l'unico modo di distinguere una scrittura ignorata da una
        # scrittura accolta e non mostrata.
        with ControlPad() as pad:
            colours = pad.read_indicators()
        return {"colors": [list(c) for c in colours] if colours else None}

    if cmd == "write_session":
        macros = [(m["slot"], m["tasto"], _eventi_da_macro(m), m["nome"])
                  for m in req.get("macros", [])]
        remaps = {int(k): v for k, v in req.get("remaps", {}).items()}
        # {"color1": [r,g,b,a], "color2": [...], "speed": n}: finisce in tutti
        # gli slot del blob di profilo, cioè in quello che il pad conserva.
        lighting = req.get("lighting")
        profile_keys = {int(k): v for k, v in req.get("profile_keys", {}).items()} \
            if req.get("profile_keys") else None
        indicators = [tuple(c) for c in req.get("indicators", [])] or None
        if indicators:
                _colori_fissi = indicators
        session_scrivi(macros=macros, remaps=remaps, lighting=lighting,
                        profile_keys=profile_keys, indicators=indicators)
        return {}

    raise ValueError(f"comando sconosciuto: {cmd!r}")


def _poll_connection():
    last = None
    while True:
        present = _device_present()
        if present != last:
            _event(event="connection", present=present)
            last = present
        time.sleep(POLL_INTERVAL)


def _chiudi(segnale=None, _frame=None):
    """Uscita ordinata: i LED indicatori tornano ai colori fissi.

    Serve perché il registro degli indicatori sopravvive allo scollegamento:
    senza questo passaggio, chiudere l'app durante un'animazione lascia il pad
    sull'ultimo fotogramma, e lì resta anche staccando e riattaccando il cavo.
    Non c'è modo di coprire il caso del cavo strappato *durante* l'animazione —
    il device è già andato quando lo si scopre — ma quello si rimedia al
    collegamento successivo, che riapplica la configurazione.
    """
    _log(f"=== chiusura (segnale {segnale}) ===")
    _ripristina_fissi()
    if segnale is not None:
        sys.exit(0)


def main():
    _log("=== motore avviato ===")
    # `Process.terminate()` dal lato Swift manda SIGTERM: senza gestore Python
    # esce di colpo e i LED restano dove sono.
    for segnale in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(segnale, _chiudi)

    threading.Thread(target=_poll_connection, daemon=True).start()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        req = None
        try:
            req = json.loads(line)
            cmd = req.get("cmd")
            # I fotogrammi di un'animazione sono decine al secondo: loggarli
            # tutti seppellirebbe qualunque cosa utile.
            if not (cmd == "set_indicators" and req.get("stream")):
                _log(f"-> {cmd} {json.dumps({k: v for k, v in req.items() if k not in ('id', 'cmd')})[:200]}")
            result = handle(req)
            _reply(req["id"], ok=True, **result)
        except Exception as exc:
            id_ = req.get("id") if isinstance(req, dict) else None
            _log(f"!! {exc}\n{traceback.format_exc()}")
            _reply(id_, ok=False, error=str(exc))

    # Stdin chiuso: l'app è stata chiusa, o è caduta. In entrambi i casi il
    # motore è l'ultimo a poter parlare col pad.
    _log("=== stdin chiuso, motore in uscita ===")
    _chiudi()


if __name__ == "__main__":
    main()
