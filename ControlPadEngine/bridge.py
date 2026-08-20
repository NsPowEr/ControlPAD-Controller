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

import controlpad
import effects
import indicatori
from controlpad import ControlPad, VID, PID
from macro import events_for, events_for_combo, EventList, PRESS
from session import PASSO_PROFILO, scrivi as session_scrivi

POLL_INTERVAL = 2.0      # ogni quanto si ricontrolla l'elenco USB
LETTURA_MS = 25          # timeout della read: e lui a dare il ritmo al thread
DRENAGGIO_MAX = 64       # report letti di fila prima di ricontrollare la pausa
INTERVALLO_STATO = 0.25  # ogni quanto si chiede al pad banco e modalita

# Le due interrogazioni con cui si sa cosa sta facendo il pad. Sono comandi
# normali, con la loro risposta, non report spontanei — ed e per questo che
# reggono su macOS: vedi _interroga_stato.
CHIEDI_BANCO = b"\x52\x00\x00\x00"
CHIEDI_MODALITA = b"\x52\x28\x00\x00"

# L'handle in ascolto sull'interfaccia vendor. **Appartiene al solo thread di
# polling**: chiuderlo da fuori mentre quel thread e fermo dentro `read()` e
# una close() concorrente su un descrittore in uso, che in hidapi non e
# definita e sul backend macOS puo far cadere il processo. Chi ha bisogno che
# il device resti libero lo chiede con `_ferma_polling()` e aspetta.
_listen_dev = None

# Handshake fra il thread dei comandi e quello di ascolto. Serve una Condition
# e non due Event: con gli Event c'e sempre una finestra fra "l'ascolto alza la
# bandiera di fermo" e "i comandi la abbassano" in cui la bandiera resta alzata
# da un giro precedente, e chi chiede l'esclusiva se la prende senza che il
# device sia stato mollato davvero. Qui le due variabili cambiano solo sotto il
# lock, quindi quella finestra non esiste.
_stato_ascolto = threading.Condition()
_ascolto_richiesto = True     # i comandi vogliono che l'ascolto giri
_ascolto_in_corso = False     # l'ascolto ha il device in mano adesso
_apertura_gia_fallita = False  # per non ripetere lo stesso avviso nel log

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


_stdout_lock = threading.Lock()


def _scrivi(riga):
    """Una riga per volta.

    Il thread dei comandi e quello di ascolto scrivono sullo stesso stdout, e
    `write` non e atomico: due righe intercalate arriverebbero all'app come un
    JSON spezzato a meta, che il decoder scarta insieme all'evento che
    portava. Prima il thread di ascolto parlava tre volte al secondo e la cosa
    non si vedeva; adesso che parla appena il pad dice qualcosa, si vedrebbe.
    """
    with _stdout_lock:
        sys.stdout.write(riga + "\n")
        sys.stdout.flush()


def _reply(id_, **fields):
    _scrivi(json.dumps({"id": id_, **fields}, separators=(",", ":")))


def _event(**fields):
    _scrivi(json.dumps(fields, separators=(",", ":")))


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
            pad.set_indicators(_colori_fissi, commit=True, banco=_banco_noto())
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
                # L'animazione tiene il device per tutta la sua durata, e su
                # macOS un secondo `open_path` non riesce: il thread di
                # ascolto resta fuori, e finche l'app mostra i LED di profilo
                # animati — cioe quasi sempre — profilo ed effetto smettono di
                # seguire il pad. Nel diario si vedeva come "ascolto in
                # attesa, device occupato: open failed" subito dopo ogni
                # start_indicator_effect. Qui l'interrogazione viaggia
                # sull'handle dell'animazione, che e gia aperto.
                banco = _banco_noto()
                if banco is None:
                    banco = pad.banco_attivo()
                n, sec, saltati = indicatori.riproduci_finche(
                    pad, fotogramma, ferma, banco=banco,
                    fra_i_fotogrammi=lambda p: _interroga_stato(p.dev),
                    ogni=INTERVALLO_STATO)
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

    # Zittire l'ascolto costa l'attesa dell'handshake, quindi lo si fa solo
    # per i comandi che prendono il device per se. I comandi di sola lettura
    # non lo aprono affatto, e i fotogrammi di un'animazione pilotata da fuori
    # (`set_indicators` con `stream`) girano su un handle persistente che
    # convive gia con quello di ascolto — come ci convive il thread degli
    # indicatori, che resta acceso mentre il polling riparte.
    esclusivo = cmd not in SOLA_LETTURA and not (
        cmd == "set_indicators" and req.get("stream"))
    if esclusivo:
        _ferma_polling()
    try:

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
            # Come per il banco: la modalita l'ha scelta l'app, quindi non
            # torna indietro come se l'avesse cambiata l'utente sul pad.
            if req["mode"] in effects.SLOT_ORDER:
                _fissa_stato("modalita", effects.SLOT_ORDER.index(req["mode"]))
            return {}

        if cmd == "get_state":
            # Dove si trova il pad *adesso*, chiesto e non aspettato. L'app
            # parte col profilo 1 selezionato e non ha nessun altro modo di
            # saperlo: senza, scrivere subito dopo l'avvio mandava la
            # configurazione nel banco 0 mentre il pad stava altrove, e i tasti
            # premuti eseguivano il banco vero. Da fuori si vedeva come
            # "funziona un profilo solo".
            with ControlPad() as pad:
                b = pad._send(CHIEDI_BANCO, "banco")
                m = pad._send(CHIEDI_MODALITA, "modalita")
            stato = {}
            if b is not None and _stato_valido("banco", b[4]):
                stato["profile"] = b[4]
                _fissa_stato("banco", b[4])
            if m is not None and _stato_valido("modalita", m[4]):
                stato["mode"] = m[4]
                _fissa_stato("modalita", m[4])
            return stato

        if cmd == "set_active_profile":
            # L'app lo manda da quando esiste il selettore di banco, ma qui
            # non c'era: nel diario del motore restava come "comando
            # sconosciuto: 'set_active_profile'", e cambiare banco dall'app
            # non faceva niente. Il comando USB era gia scritto e provato.
            banco = int(req["profile"])
            if not 0 <= banco < 24:
                raise ValueError(f"banco fuori scala: {banco}")
            with ControlPad() as pad:
                pad.set_profile(banco)
            # Il banco l'ha cambiato l'app, non l'utente sul pad.
            _fissa_stato("banco", banco)
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
                    pad.set_indicators(colors, commit=True, banco=_banco_noto())
                return {}
            try:
                _pad_persistente().set_indicators(colors, banco=_banco_noto())
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
                    pad.set_indicators(colors, commit=True, banco=_banco_noto())
            return {}

        if cmd == "read_indicators":
            # Rilettura dell'indirizzo 0x00fc: dice cosa il device *ha* davvero,
            # che è l'unico modo di distinguere una scrittura ignorata da una
            # scrittura accolta e non mostrata.
            with ControlPad() as pad:
                colours = pad.read_indicators(banco=_banco_noto())
            return {"colors": [list(c) for c in colours] if colours else None}

        if cmd == "write_session":
            # Il banco di destinazione. La sessione **non porta con se** il
            # banco in cui deve finire: si scrive in quello attivo in quel
            # momento. Misurato sul device — scritta una rimappatura mentre il
            # pad era sul banco 5, `52 20 35 00` la rilegge solo dal banco 5,
            # e dai banchi 2 e 7 torna il valore di fabbrica.
            #
            # Senza questo passaggio la scrittura finiva dove il pad si
            # trovava, cioe sempre nello stesso banco qualunque profilo si
            # stesse modificando nell'app: uno funzionava e gli altri
            # ventitre no. Va fatto qui e non dal lato Swift perche qui e
            # dentro la sezione esclusiva, con l'animazione ferma e l'ascolto
            # zitto: fra la scelta del banco e la scrittura non si infila
            # nessuno.
            banco = req.get("profile")
            if banco is not None:
                banco = int(banco)
                if not 0 <= banco < 24:
                    raise ValueError(f"banco fuori scala: {banco}")
                with ControlPad() as pad:
                    pad.set_profile(banco)
                _fissa_stato("banco", banco)

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
            # Quanti report non hanno ricevuto la loro conferma. Zero e l'unico
            # valore che dica che la scrittura e passata tutta: il device ACKa
            # anche quello che non esegue, ma non ACKare del tutto e un guasto
            # visibile, e l'app deve poterlo dire invece di mostrare un successo.
            # Gli indicatori vanno nello slot del banco che si sta scrivendo,
            # non in quello su cui il pad si trovava prima.
            senza_ack = session_scrivi(macros=macros, remaps=remaps,
                                        lighting=lighting,
                                        profile_keys=profile_keys,
                                        indicators=indicators,
                                        banco=banco if banco is not None
                                        else (_banco_noto() or 0))
            if senza_ack:
                _log(f"!! scrittura sessione: {senza_ack} report senza ACK")

            # Riletta, non dedotta. Il device ACKa anche quello che non
            # esegue — e tutta la storia di questo protocollo — quindi
            # "missing_acks: 0" non dice che la configurazione sia finita
            # dove doveva. Qui si richiede al pad in che banco si trova e
            # cosa ha in keymap, e si riferisce quello che risponde.
            verifica = _verifica_scrittura(banco, remaps, macros)
            return {"missing_acks": senza_ack, **verifica}

        raise ValueError(f"comando sconosciuto: {cmd!r}")
    finally:
        if esclusivo:
            _riprendi_polling()



def _chiudi_listen_dev():
    """Chiude l'handle di ascolto. Solo dal thread di polling: vedi _listen_dev."""
    global _listen_dev
    if _listen_dev is not None:
        try:
            _listen_dev.close()
        except Exception:
            pass
        _listen_dev = None


def _ferma_polling(timeout=2.0):
    """Chiede l'esclusiva sul device e aspetta che l'ascolto l'abbia mollato.

    Aspettare e il punto: chiudere l'handle dal thread dei comandi mentre
    l'altro e fermo dentro `read()` significa liberargli sotto i piedi la
    struttura su cui sta bloccato. Qui invece il descrittore lo chiude sempre
    chi lo possiede, e il comando parte solo dopo. Con `read()` a
    `LETTURA_MS` l'attesa e di norma sotto i 25 ms.
    """
    global _ascolto_richiesto
    with _stato_ascolto:
        _ascolto_richiesto = False
        _stato_ascolto.notify_all()
        if not _stato_ascolto.wait_for(lambda: not _ascolto_in_corso, timeout):
            # Non si blocca il comando per un thread che non risponde: al
            # massimo si ricade nel vecchio comportamento, due handle insieme.
            _log("!! l'ascolto non ha mollato il device entro il timeout")


def _riprendi_polling():
    global _ascolto_richiesto
    with _stato_ascolto:
        _ascolto_richiesto = True
        _stato_ascolto.notify_all()


def _dormi(secondi):
    """Attesa interrompibile: una richiesta di esclusiva non aspetta tutto."""
    with _stato_ascolto:
        _stato_ascolto.wait_for(lambda: not _ascolto_richiesto, secondi)


def _apri_listen_dev():
    """Apre l'interfaccia vendor in ascolto. Torna se il pad risulta collegato.

    Il valore di ritorno dice se il *device* c'e, non se l'apertura e riuscita:
    un pad presente ma momentaneamente non apribile resta presente per l'app, e
    il giro dopo si riprova.

    L'apertura fallisce regolarmente, e non e un guasto: su macOS il secondo
    `open_path` sullo stesso device non riesce finche un altro thread lo
    tiene, quindi per tutta la durata di un'animazione degli indicatori qui si
    prende "open failed" ogni giro. Il log lo dice una volta e poi tace fino
    alla prossima riuscita — nel diario di una sessione vera quel messaggio
    ripetuto occupava centinaia di righe. Gli eventi di quel periodo non
    vanno persi lo stesso: li raccoglie `controlpad.OSSERVATORE`.
    """
    global _listen_dev, _apertura_gia_fallita
    path = next((d["path"] for d in hid.enumerate(VID, PID)
                 if d.get("usage_page") == 0xFF00), None)
    if path is None:
        return False
    try:
        d = hid.device()
        d.open_path(path)
        d.set_nonblocking(0)          # il ritmo lo da il timeout della read
        _listen_dev = d
        _apertura_gia_fallita = False
    except Exception as exc:
        if not _apertura_gia_fallita:
            _log(f"   ascolto in attesa, device occupato: {exc}")
            _apertura_gia_fallita = True
        _listen_dev = None
    return True


def _interpreta_report(rep):
    """Traduce in evento un report che il pad manda senza che glielo si chieda.

    Le forme viste nelle catture, tutte lunghe 64 byte:

        52 00 00 00 <banco>            banco di profilo attivo, 0x00..0x17
        52 28 00 00 <slot>             modalita di illuminazione attiva
        43 01 00 00 <indice> c0 | 40   tasto premuto (c0) o rilasciato (40)

    Il terzo e il piu frequente di tutti — arriva a ogni pressione, comprese
    quelle dei tasti che battono un carattere — ed e quello che riempiva il
    buffer del sistema mentre il thread dormiva. Qui si riconosce e si scarta:
    va letto per liberare la coda, non serve all'app.
    """
    if rep[:1] == b"\x00":
        # Se hidapi anteponesse un Report ID il pacchetto vero comincia dopo.
        # Nessun report del pad comincia per 00, quindi toglierlo non toglie
        # niente di vero.
        rep = rep[1:]
    if len(rep) < 6:
        return

    testa = rep[:4]
    if testa == b"\x52\x00\x00\x00":
        if _stato_valido("banco", rep[4]):
            # Un annuncio spontaneo e gia di per se un cambiamento, quindi
            # vale anche se e la prima cosa che il motore sente.
            _riferisci("banco", rep[4], annuncia_il_primo=True)
    elif testa == b"\x52\x28\x00\x00":
        if _stato_valido("modalita", rep[4]):
            _riferisci("modalita", rep[4], annuncia_il_primo=True)


# Lo stato che il pad ha detto l'ultima volta, da qualunque strada sia
# arrivato. Ci passano tutti e due i modi di saperlo — l'annuncio spontaneo che
# si vede su Windows e l'interrogazione che serve su macOS — cosi lo stesso
# cambiamento non viene riferito due volte se per caso li si sente entrambi.
_stato_pad = {}
_stato_pad_lock = threading.Lock()


def _riferisci(chiave, valore, annuncia_il_primo):
    """Riferisce all'app un cambio di stato, una volta sola.

    `annuncia_il_primo` distingue le due strade. Un annuncio spontaneo del pad
    e per definizione un cambiamento, quindi vale anche se e la prima cosa che
    si sente. Il primo giro di interrogazione invece non e un cambiamento: e
    solo il motore che scopre dov'era il pad quando e partito, e riferirlo
    farebbe muovere l'interfaccia all'avvio senza che nessuno abbia toccato
    niente.
    """
    with _stato_pad_lock:
        primo = chiave not in _stato_pad
        if _stato_pad.get(chiave) == valore:
            return False
        _stato_pad[chiave] = valore

    if primo and not annuncia_il_primo:
        _log(f"   stato iniziale del pad: {chiave} = {valore}")
        return False


    _log(f"   <- {chiave} cambiata sul pad: {valore}")
    if chiave == "banco":
        _event(event="hardware_profile_changed", profile=valore)
    else:
        _event(event="hardware_mode_changed", slot=valore)
    return True


def _stato_valido(chiave, valore):
    """Se questo numero e uno stato vero del pad, o un residuo da ignorare.

    Il registro `51 28` fa doppio servizio: ci si scrive la modalita da
    attivare, ma anche il comando di applicazione, che e `51 28 00 00 ff` —
    lo manda il software ufficiale, 120 volte nelle catture, e lo manda pure
    `ControlPad._finish`. Rileggendolo subito dopo con `52 28 00 00` torna
    quindi **255**, che non e una modalita: e "ho appena applicato".

    Misurato sul device: `51 28 00 00 01` -> rilegge 1; l'applicazione ->
    rilegge 255; `51 28 00 00 07` -> rilegge 7; un cambio di banco -> rilegge
    la modalita di quel banco. Il 255 non va riferito. Prima ci finiva
    dentro un `hardware_mode_changed` con `slot: 255`, che l'app scartava in
    silenzio perche fuori dai quattordici slot — la sincronia dell'effetto
    moriva li senza un errore da nessuna parte.
    """
    if chiave == "banco":
        return valore < 24
    return valore < len(effects.SLOT_ORDER)


def _verifica_scrittura(banco_chiesto, remaps, macros=()):
    """Rilegge dal pad dove e finita la sessione appena scritta.

    Restituisce `{"profile_written": n, "verified": bool}`. `verified` e falso
    quando il banco riletto non e quello chiesto, o quando una rimappatura
    richiesta non si rilegge: sono i due modi in cui una scrittura ACKata puo
    non essere servita a niente, e finora nessuno dei due lasciava traccia.
    """
    esito = {}
    try:
        with ControlPad() as pad:
            risposta = pad._send(CHIEDI_BANCO, "banco")
            if risposta is not None:
                esito["profile_written"] = risposta[4]

            atteso = {}
            for tasto, azione in (remaps or {}).items():
                if azione in PASSO_PROFILO:
                    continue
                letto = pad._send(bytes([0x52, 0x20, tasto, 0x00]), "keymap")
                if letto is not None:
                    atteso[tasto] = letto[4] | (letto[5] << 8)

            # `52 18 <slot> 00` -> `<tasto> <tipo>`, con `ff 3f` = slot vuoto.
            # Va guardato quanto la keymap: una sessione fatta di sole macro
            # passava la verifica senza che nessuno avesse controllato niente,
            # perche di rimappature non ne aveva.
            slot_letti = {}
            for slot, tasto, _eventi, _nome in macros or ():
                letto = pad._send(bytes([0x52, 0x18, slot, 0x00]), "macro")
                if letto is not None:
                    slot_letti[slot] = (letto[4], letto[5])
    except Exception as exc:
        _log(f"!! verifica della scrittura non riuscita: {exc}")
        return esito

    problemi = []
    if banco_chiesto is not None and esito.get("profile_written") != banco_chiesto:
        problemi.append(f"chiesto il banco {banco_chiesto}, "
                        f"il pad e sul {esito.get('profile_written')}")
    for tasto, voluto in (remaps or {}).items():
        if voluto in PASSO_PROFILO:
            # I due codici "scorri i profili" sono convenzioni dell'app, non
            # azioni che il dispositivo conosca: sul pad quei tasti portano
            # `00ff` e la funzione sta nella loro assenza da `51 94`.
            # Cercarli nella keymap faceva fallire la verifica su una
            # scrittura riuscita, e l'app ne faceva un errore rosso.
            continue
        if atteso.get(tasto) != voluto:
            problemi.append(f"tasto 0x{tasto:02x}: chiesto 0x{voluto:04x}, "
                            f"riletto 0x{atteso.get(tasto, 0):04x}")
    for slot, tasto, _eventi, _nome in macros or ():
        if slot_letti.get(slot) != (tasto, PRESS):
            letto = slot_letti.get(slot)
            come = "slot vuoto" if letto == (0xFF, 0x3F) else f"{letto}"
            problemi.append(f"macro slot {slot}: chiesto il tasto "
                            f"0x{tasto:02x}, riletto {come}")

    esito["verified"] = not problemi
    if problemi:
        _log("!! la scrittura non si rilegge: " + " · ".join(problemi[:4]))
    else:
        _log(f"   scrittura verificata sul banco {esito.get('profile_written')}"
             f": {len(remaps or {})} rimappature, {len(macros or ())} macro")
    return esito


def _banco_noto():
    """Il banco su cui il pad si trova, per quanto ne sa il motore.

    Serve a ogni scrittura degli indicatori: i quattro LED hanno uno slot per
    banco, e scrivere quello sbagliato non da errore — il device conferma e
    non si accende niente. `None` significa "non lo so ancora": chi scrive
    chiede al pad, che costa un report ma non sbaglia bersaglio.
    """
    with _stato_pad_lock:
        return _stato_pad.get("banco")


def _fissa_stato(chiave, valore):
    """Registra uno stato senza riferirlo, perche a cambiarlo e stata l'app.

    Senza questo, il primo giro di interrogazione dopo un comando vedrebbe il
    valore nuovo, lo troverebbe diverso da quello noto, e lo rimanderebbe
    all'app come se l'avesse cambiato l'utente sul pad. L'app riceverebbe
    l'eco della propria mossa.
    """
    with _stato_pad_lock:
        _stato_pad[chiave] = valore


def _interroga_stato(dev):
    """Chiede al pad banco e modalita, e riferisce solo quello che e cambiato.

    Perche interrogare invece di ascoltare. Il pad annuncia da solo i propri
    cambi di stato — `52 00 00 00 <banco>` e `52 28 00 00 <slot>` — e su
    Windows quegli annunci si vedono, tant'e che sono nelle catture. **Su
    macOS non arrivano.** Misurato: trenta secondi con l'interfaccia vendor
    aperta e la coda letta di continuo, zero report spontanei; le stesse due
    interrogazioni, mandate a mano sullo stesso handle, rispondono all'istante
    (`banco 8`, `modalita 4`). Il backend darwin di hidapi consegna a un handle
    le risposte ai comandi di quell'handle, e i report non richiesti finiscono
    altrove.

    Aspettare un annuncio che non arrivera mai e il motivo per cui su macOS
    profilo ed effetto restavano fermi nell'app mentre sul pad cambiavano.
    Chiedere funziona ovunque: e un comando come gli altri, con la sua
    risposta, e costa due report ogni INTERVALLO_STATO.

    Il ramo di ascolto resta comunque: su Windows arriva prima, e la coda va
    tenuta vuota in ogni caso.
    """
    for chiave, comando in (("banco", CHIEDI_BANCO),
                            ("modalita", CHIEDI_MODALITA)):
        dev.write(b"\x00" + comando.ljust(64, b"\x00"))
        # `attendi_ack` legge finche non torna *questo* opcode: i report che
        # scarta per strada passano da controlpad.OSSERVATORE, quindi anche
        # qui non si perde niente di quello che il pad dicesse da solo.
        risposta = controlpad.attendi_ack(dev, comando[:2], timeout_ms=150)
        if risposta is None:
            continue

        if not _stato_valido(chiave, risposta[4]):
            continue
        # Il primo giro tace: e un evento, e arriverebbe *dopo* che l'app ha
        # gia applicato l'illuminazione della bozza, sostituendogliela sotto —
        # nel diario si vedeva come uno `start_indicator_effect` seguito dallo
        # `stop` un istante dopo, "animazione chiusa: 1 fotogrammi". Lo stato
        # di partenza l'app se lo fa dire da `get_state`, che risponde quando
        # lei lo chiede invece di arrivare a sorpresa.
        _riferisci(chiave, risposta[4], annuncia_il_primo=False)


def _poll_connection():
    """Ascolto continuo del pad, in un thread suo.

    Il ritmo lo da il timeout della `read`, non uno sleep in fondo al ciclo.
    Con lo sleep, ogni pacchetto arrivato faceva tornare la `read` all'istante
    e poi il thread si fermava lo stesso per tutta la durata della pausa: tre
    letture al secondo, con il resto in coda nel buffer del sistema. Premendo
    i tasti — che generano un report ciascuno — la coda cresceva piu in fretta
    di quanto la si svuotasse, e un cambio di banco fatto a mano sul pad
    arrivava all'app con secondi di ritardo o si perdeva.

    Adesso una `read` scaduta a vuoto e l'unica attesa: quando non c'e niente
    da leggere il thread e fermo in una `read` bloccante, che non costa CPU;
    quando c'e, torna subito e il ciclo interno svuota la coda in un fiato.
    """
    global _listen_dev, _ascolto_in_corso
    presente = None
    ultimo_elenco = 0.0
    ultimo_stato = 0.0

    def segnala(stato):
        nonlocal presente
        if stato != presente:
            presente = stato
            _event(event="connection", present=stato)

    while True:
        try:
            # Il device si molla e si riprende sempre da qui, cioe dal thread
            # che lo possiede, e sempre sotto il lock: chi ha chiesto
            # l'esclusiva vede `_ascolto_in_corso` falso solo quando l'handle
            # e gia chiuso.
            with _stato_ascolto:
                if not _ascolto_richiesto:
                    _chiudi_listen_dev()
                    _ascolto_in_corso = False
                    _stato_ascolto.notify_all()
                    _stato_ascolto.wait_for(lambda: _ascolto_richiesto)
                _ascolto_in_corso = True

            if _listen_dev is None:
                ultimo_elenco = time.monotonic()
                segnala(_apri_listen_dev())
                if _listen_dev is None:
                    _dormi(POLL_INTERVAL)
                    continue

            # Rete di sicurezza. Con l'handle aperto lo scollegamento lo
            # scopre la lettura, che fallisce subito; ma se per qualunque
            # motivo restasse muta invece di fallire, senza questo controllo
            # l'app resterebbe convinta che il pad c'e. Un enumerate ogni
            # POLL_INTERVAL e la stessa frequenza di prima della riscrittura.
            if time.monotonic() - ultimo_elenco >= POLL_INTERVAL:
                ultimo_elenco = time.monotonic()
                if not _device_present():
                    _chiudi_listen_dev()
                    segnala(False)
                    continue
                segnala(True)

            try:
                # 1. Si drena quello che il pad ha mandato da solo. Su Windows
                #    e da li che arrivano i cambi di stato; su macOS non arriva
                #    niente, ma leggere non costa e la coda va tenuta vuota.
                for _ in range(DRENAGGIO_MAX):
                    dati = _listen_dev.read(64, timeout_ms=LETTURA_MS)
                    if not dati:
                        break            # coda vuota: il timeout e scaduto
                    _interpreta_report(bytes(dati))

                # 2. Si chiede al pad come sta. E questo il passo che fa
                #    funzionare la sincronia su macOS.
                if time.monotonic() - ultimo_stato >= INTERVALLO_STATO:
                    ultimo_stato = time.monotonic()
                    _interroga_stato(_listen_dev)
            except Exception as exc:
                _log(f"!! lettura dal pad interrotta: {exc}")
                _chiudi_listen_dev()
                ultimo_elenco = time.monotonic()
                segnala(_device_present())
                _dormi(POLL_INTERVAL)

        except Exception as exc:
            # Il thread non deve morire: se muore l'app non sa piu nemmeno
            # quando il pad viene staccato, e non c'e nessuno che lo riavvii.
            _log(f"!! ciclo di ascolto: {exc}\n{traceback.format_exc()}")
            _chiudi_listen_dev()
            _dormi(POLL_INTERVAL)


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

    # I report che l'attesa dell'ACK scarta passano anche di qui: e l'unico
    # modo di vedere un cambio di banco fatto a mano mentre il device e in
    # mano a qualcun altro — un'animazione degli indicatori, o una scrittura
    # di sessione — perche in quei momenti il secondo handle non si apre.
    controlpad.OSSERVATORE = _interpreta_report

    threading.Thread(target=_poll_connection, daemon=True,
                     name="ascolto").start()

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
