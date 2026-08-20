"""Il thread di ascolto del bridge, con un hidapi finto al posto del pad.

Quello che si vuole tenere fermo e il ritmo. La versione precedente del ciclo
faceva `time.sleep(0.3)` in fondo a ogni giro: una `read` che tornava subito
perche c'era un pacchetto veniva comunque seguita da 300 ms di pausa, quindi
il motore leggeva al massimo tre report al secondo. Il pad ne manda uno per
ogni pressione di tasto, quindi bastava usarlo per riempire il buffer del
sistema, e i cambi di banco fatti a mano — che sono gli eventi che l'app deve
vedere subito — arrivavano in ritardo o si perdevano.

    python3 -m unittest discover -s ControlPadEngine/tests
"""

import collections
import json
import os
import sys
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import controlpad                                        # noqa: E402
import effects                                          # noqa: E402
import bridge                                           # noqa: E402


def rapporto(hexstr):
    """Un report da 64 byte come li manda il pad."""
    return list(bytes.fromhex(hexstr).ljust(64, b"\x00"))


class HidFinto:
    """Il minimo di hidapi che il thread di ascolto usa, e un registratore.

    Tiene anche la contabilita che serve alle asserzioni: quante volte e stato
    aperto e chiuso il device, quante `read` sono partite, quante
    enumerazioni. Una `read` su un handle gia chiuso non torna vuota ma
    solleva: se il thread dei comandi chiudesse il device sotto il thread di
    ascolto, il test lo direbbe invece di dipendere da come reagisce hidapi.
    """

    def __init__(self):
        self.lock = threading.Lock()
        self.coda = collections.deque()
        self.presente = True
        self.scollegato = False
        self.aperti = self.chiusi = self.letture = self.enumerazioni = 0
        # Lo stato che il pad riferisce quando lo si interroga con 52 00 / 52 28.
        self.banco, self.modalita = 8, 4
        self.device = self._Device            # hid.device()

    def enumerate(self, vid=0, pid=0):
        with self.lock:
            self.enumerazioni += 1
            presente = self.presente
        return [{"path": b"/finto", "usage_page": 0xFF00}] if presente else []

    def accoda(self, *reports):
        with self.lock:
            self.coda.extend(reports)

    def coda_vuota(self):
        with self.lock:
            return not self.coda

    @property
    def _Device(finto):                       # noqa: N805 - fabbrica, non metodo
        class Device:
            def __init__(self):
                self.chiuso = False
                self.attesa = None        # opcode dell'ultima interrogazione

            def open_path(self, path):
                with finto.lock:
                    finto.aperti += 1

            def set_nonblocking(self, valore):
                pass

            def write(self, dati):
                if self.chiuso:
                    raise AssertionError("write su un handle gia chiuso")
                with finto.lock:
                    if finto.scollegato:
                        raise OSError("device scollegato")
                self.attesa = bytes(dati)[1:3]

            def read(self, lunghezza, timeout_ms=0):
                if self.chiuso:
                    raise AssertionError(
                        "read su un handle gia chiuso: il device e stato "
                        "chiuso da un thread che non lo possiede")
                with finto.lock:
                    finto.letture += 1
                    if finto.scollegato:
                        raise OSError("device scollegato")
                    if self.attesa is not None:
                        # Risposta all'interrogazione, come la manda il pad.
                        opcode, self.attesa = self.attesa, None
                        valore = (finto.banco if opcode == b"\x52\x00"
                                  else finto.modalita)
                        return list(opcode + b"\x00\x00" + bytes([valore])
                                    + bytes(59))
                    if finto.coda:
                        return finto.coda.popleft()
                time.sleep(timeout_ms / 1000)
                return []

            def close(self):
                with finto.lock:
                    finto.chiusi += 1
                self.chiuso = True

        return Device


class AscoltoTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.hid_vero = bridge.hid
        cls.scrivi_vero = bridge._scrivi
        cls.log_vero = bridge._log

        cls.finto = HidFinto()
        cls.righe = []
        cls.righe_lock = threading.Lock()

        def raccogli(riga):
            with cls.righe_lock:
                cls.righe.append(json.loads(riga))

        bridge.hid = cls.finto
        bridge._scrivi = raccogli
        bridge._log = lambda testo: None

        with bridge._stato_pad_lock:
            bridge._stato_pad.clear()
        cls.thread = threading.Thread(target=bridge._poll_connection,
                                      daemon=True, name="ascolto-test")
        cls.thread.start()
        cls.attendi(lambda: bridge._listen_dev is not None)

    @classmethod
    def tearDownClass(cls):
        bridge._ferma_polling()               # il thread molla il device e si parcheggia
        bridge.hid = cls.hid_vero
        bridge._scrivi = cls.scrivi_vero
        bridge._log = cls.log_vero

    @staticmethod
    def attendi(condizione, timeout=5.0):
        scadenza = time.monotonic() + timeout
        while time.monotonic() < scadenza:
            if condizione():
                return True
            time.sleep(0.005)
        return False

    @classmethod
    def eventi(cls, nome):
        with cls.righe_lock:
            return [r for r in cls.righe if r.get("event") == nome]

    def test_01_connessione_annunciata_una_volta(self):
        self.assertEqual([e["present"] for e in self.eventi("connection")], [True])
        self.assertEqual(self.finto.aperti, 1)

    def test_02_drena_la_coda_invece_di_dormirci_sopra(self):
        # 200 pressioni di tasto piu i due eventi che all'app servono davvero.
        # Col vecchio ciclo a tre letture al secondo ci volevano oltre 60 s, e
        # nel frattempo il buffer del sistema traboccava.
        self.finto.accoda(*[rapporto("4301000005c0") for _ in range(200)])
        self.finto.accoda(rapporto("5200000007"), rapporto("5228000003"))

        inizio = time.monotonic()
        self.assertTrue(self.attendi(self.finto.coda_vuota, timeout=3.0),
                        "la coda non si e svuotata")
        durata = time.monotonic() - inizio
        self.assertLess(durata, 1.0, f"202 report drenati in {durata:.2f}s")

        self.assertTrue(self.attendi(
            lambda: self.eventi("hardware_profile_changed")))
        self.assertEqual([e["profile"] for e in
                          self.eventi("hardware_profile_changed")], [7])
        self.assertEqual([e["slot"] for e in
                          self.eventi("hardware_mode_changed")], [3])

    def test_03_le_pressioni_di_tasto_non_diventano_eventi(self):
        # 43 01 arriva a ogni pressione, comprese quelle dei tasti che battono
        # un carattere: va letto per liberare la coda, non riferito all'app.
        with self.righe_lock:
            nomi = {r.get("event") for r in self.righe}
        self.assertEqual(nomi, {"connection", "hardware_profile_changed",
                                "hardware_mode_changed"})

    def test_04_esclusiva_il_device_lo_molla_chi_lo_possiede(self):
        chiusi = self.finto.chiusi
        inizio = time.monotonic()
        bridge._ferma_polling()
        attesa = time.monotonic() - inizio
        try:
            self.assertEqual(self.finto.chiusi, chiusi + 1)
            self.assertIsNone(bridge._listen_dev)
            self.assertLess(attesa, 1.0, f"esclusiva ottenuta in {attesa:.2f}s")
            letture = self.finto.letture
            time.sleep(0.2)
            self.assertEqual(self.finto.letture, letture,
                             "l'ascolto legge ancora durante l'esclusiva")
        finally:
            bridge._riprendi_polling()
        self.assertTrue(self.attendi(lambda: bridge._listen_dev is not None))

    def test_05_esclusiva_e_rilascio_ripetuti_non_si_incastrano(self):
        # Con due Event al posto della Condition, la bandiera di "fermo" alzata
        # in un giro precedente faceva tornare subito la richiesta successiva:
        # il comando partiva mentre il device era ancora dell'ascolto.
        for _ in range(30):
            bridge._ferma_polling(timeout=1.0)
            self.assertIsNone(bridge._listen_dev)
            bridge._riprendi_polling()
        self.assertTrue(self.attendi(lambda: bridge._listen_dev is not None))

    def test_06_scollegamento_visto_dalla_read(self):
        with self.finto.lock:
            self.finto.scollegato = True
            self.finto.presente = False
        self.assertTrue(self.attendi(
            lambda: any(e["present"] is False for e in self.eventi("connection"))),
            "scollegamento non riferito")

        with self.finto.lock:
            self.finto.scollegato = False
            self.finto.presente = True
        self.assertTrue(self.attendi(
            lambda: self.eventi("connection")[-1]["present"] is True,
            timeout=6.0), "riattacco non riferito")

    def test_07_a_riposo_non_interroga_il_bus_a_raffica(self):
        # Con l'handle aperto la presenza la dice la read; l'elenco USB serve
        # solo da rete di sicurezza, ogni POLL_INTERVAL.
        self.assertTrue(self.attendi(lambda: bridge._listen_dev is not None))
        with self.finto.lock:
            prima = self.finto.enumerazioni
        time.sleep(1.0)
        with self.finto.lock:
            dopo = self.finto.enumerazioni
        self.assertLessEqual(dopo - prima, 2, "troppe enumerazioni a riposo")


class InterpretaReportTest(unittest.TestCase):
    """La decodifica dei report non richiesti, senza thread di mezzo."""

    def setUp(self):
        self.eventi = []
        self.evento_vero = bridge._event
        self.log_vero = bridge._log
        bridge._event = lambda **campi: self.eventi.append(campi)
        bridge._log = lambda testo: None
        with bridge._stato_pad_lock:
            bridge._stato_pad.clear()

    def tearDown(self):
        bridge._event = self.evento_vero
        bridge._log = self.log_vero
        with bridge._stato_pad_lock:
            bridge._stato_pad.clear()

    def test_banco_di_profilo(self):
        bridge._interpreta_report(bytes(rapporto("5200000017")))
        self.assertEqual(self.eventi,
                         [{"event": "hardware_profile_changed", "profile": 0x17}])

    def test_banco_fuori_scala_ignorato(self):
        bridge._interpreta_report(bytes(rapporto("5200000018")))
        self.assertEqual(self.eventi, [])

    def test_modalita(self):
        bridge._interpreta_report(bytes(rapporto("522800000d")))
        self.assertEqual(self.eventi,
                         [{"event": "hardware_mode_changed", "slot": 0x0D}])

    def test_report_id_davanti(self):
        # Se hidapi anteponesse un Report ID il pacchetto vero comincia dopo.
        bridge._interpreta_report(b"\x00" + bytes(rapporto("5200000005")))
        self.assertEqual(self.eventi,
                         [{"event": "hardware_profile_changed", "profile": 5}])

    def test_pressione_di_tasto_letta_e_scartata(self):
        bridge._interpreta_report(bytes(rapporto("4301000012c0")))
        bridge._interpreta_report(bytes(rapporto("430100001240")))
        self.assertEqual(self.eventi, [])

    def test_niente_falsi_positivi_su_altri_report(self):
        # La versione precedente cercava il motivo `52 00 00 00` *dentro* i
        # primi sei byte, quindi un report che se lo portava sfalsato bastava
        # a far cambiare banco all'interfaccia.
        for report in ("4220000000000001", "5280130000000000", "5220" + "1e001e00",
                       "4180", "4104", "41010000000000000052000000ff"):
            bridge._interpreta_report(bytes(rapporto(report)))
        self.assertEqual(self.eventi, [])

    def test_report_troppo_corto(self):
        bridge._interpreta_report(b"\x52\x00\x00")
        self.assertEqual(self.eventi, [])

    def test_lo_stesso_valore_non_esce_due_volte(self):
        # Lo stesso cambiamento puo arrivare da due strade: l'annuncio
        # spontaneo (Windows) e l'interrogazione (macOS). Riferirlo due volte
        # farebbe ricaricare il profilo all'app per niente.
        bridge._interpreta_report(bytes(rapporto("5200000009")))
        bridge._interpreta_report(bytes(rapporto("5200000009")))
        self.assertEqual(self.eventi,
                         [{"event": "hardware_profile_changed", "profile": 9}])

    def test_valori_diversi_passano_sempre(self):
        for banco in ("5200000003", "5200000004", "5200000003"):
            bridge._interpreta_report(bytes(rapporto(banco)))
        self.assertEqual([e["profile"] for e in self.eventi], [3, 4, 3])

    def test_banco_e_modalita_non_si_filtrano_a_vicenda(self):
        bridge._interpreta_report(bytes(rapporto("5200000003")))
        bridge._interpreta_report(bytes(rapporto("5228000003")))
        self.assertEqual(len(self.eventi), 2)


class InterrogaStatoTest(unittest.TestCase):
    """L'interrogazione attiva: e questa che fa funzionare la sincronia su macOS.

    Il pad annuncia da solo i cambi di banco e di modalita, ma su macOS quegli
    annunci non arrivano all'handle: misurati trenta secondi con la coda letta
    di continuo, zero report. Le stesse informazioni chieste con `52 00`/`52 28`
    rispondono sempre.
    """

    class DevFinto:
        """Risponde alle interrogazioni con lo stato che gli si mette dentro."""

        def __init__(self, banco, modalita):
            self.banco, self.modalita = banco, modalita
            self.scritti = []

        def write(self, dati):
            self.scritti.append(bytes(dati)[1:3])

        def read(self, lunghezza, timeout_ms=0):
            opcode = self.scritti[-1]
            valore = self.banco if opcode == b"\x52\x00" else self.modalita
            return list(opcode + b"\x00\x00" + bytes([valore]) + bytes(59))

    def setUp(self):
        self.eventi = []
        self.evento_vero, self.log_vero = bridge._event, bridge._log
        bridge._event = lambda **campi: self.eventi.append(campi)
        bridge._log = lambda testo: None
        with bridge._stato_pad_lock:
            bridge._stato_pad.clear()

    def tearDown(self):
        bridge._event, bridge._log = self.evento_vero, self.log_vero
        with bridge._stato_pad_lock:
            bridge._stato_pad.clear()

    def _riferimento(self, banco=8, modalita=4):
        """Primo giro fatto e messo da parte: da qui si guardano i cambiamenti."""
        dev = self.DevFinto(banco=banco, modalita=modalita)
        bridge._interroga_stato(dev)
        self.eventi.clear()
        return dev

    def test_il_primo_giro_fissa_il_riferimento_e_tace(self):
        # Un evento arriverebbe *dopo* che l'app ha gia applicato
        # l'illuminazione della bozza, sostituendogliela sotto: nel diario si
        # vedeva come uno start_indicator_effect seguito dallo stop un istante
        # dopo, "animazione chiusa: 1 fotogrammi". Lo stato di partenza l'app
        # se lo fa dire da `get_state`, quando lo chiede lei.
        bridge._interroga_stato(self.DevFinto(banco=8, modalita=4))
        self.assertEqual(self.eventi, [])
        self.assertEqual(bridge._stato_pad, {"banco": 8, "modalita": 4})

    def test_un_cambio_sul_pad_diventa_un_evento(self):
        dev = self._riferimento()
        dev.banco = 7                          # l'utente preme "profilo -"
        bridge._interroga_stato(dev)
        self.assertEqual(self.eventi,
                         [{"event": "hardware_profile_changed", "profile": 7}])

    def test_cambio_di_modalita(self):
        dev = self._riferimento()
        dev.modalita = 5                       # "effetto +"
        bridge._interroga_stato(dev)
        self.assertEqual(self.eventi,
                         [{"event": "hardware_mode_changed", "slot": 5}])

    def test_stato_fermo_non_produce_eventi(self):
        dev = self._riferimento()
        for _ in range(10):
            bridge._interroga_stato(dev)
        self.assertEqual(self.eventi, [])

    def test_banco_fuori_scala_ignorato(self):
        dev = self._riferimento()
        dev.banco = 200
        bridge._interroga_stato(dev)
        self.assertEqual(self.eventi, [])
        self.assertEqual(bridge._stato_pad["banco"], 8)

    def test_annuncio_spontaneo_e_interrogazione_non_si_sdoppiano(self):
        # Su Windows possono arrivare tutti e due: e lo stesso cambiamento.
        dev = self._riferimento()
        dev.banco = 3
        bridge._interpreta_report(bytes(rapporto("5200000003")))   # annuncio
        bridge._interroga_stato(dev)                               # interrogazione
        self.assertEqual(self.eventi,
                         [{"event": "hardware_profile_changed", "profile": 3}])


class OsservatoreAckTest(unittest.TestCase):
    """I report scartati da attendi_ack arrivano lo stesso all'app.

    E l'unica strada quando il device e in mano a qualcun altro: su macOS il
    secondo `open_path` fallisce mentre un'animazione o una scrittura di
    sessione tengono l'handle, quindi in quei momenti l'ascolto non esiste e
    un cambio di banco fatto a mano si vedrebbe solo qui.
    """

    class DevFinto:
        def __init__(self, reports):
            self.reports = list(reports)

        def read(self, lunghezza, timeout_ms=0):
            return self.reports.pop(0) if self.reports else []

    def setUp(self):
        self.osservati = []
        self.vero = controlpad.OSSERVATORE
        controlpad.OSSERVATORE = self.osservati.append

    def tearDown(self):
        controlpad.OSSERVATORE = self.vero

    def test_lo_scarto_viene_consegnato_e_l_ack_torna_lo_stesso(self):
        dev = self.DevFinto([
            rapporto("5200000007"),          # cambio banco, non richiesto
            rapporto("4301000005c0"),        # pressione di tasto
            rapporto("5615000000000000"),    # l'ACK che si stava aspettando
        ])
        risposta = controlpad.attendi_ack(dev, b"\x56\x15", timeout_ms=200)
        self.assertIsNotNone(risposta)
        self.assertEqual(risposta[:2], b"\x56\x15")
        self.assertEqual([bytes(r)[:5].hex() for r in self.osservati],
                         ["5200000007", "4301000005"])

    def test_un_osservatore_che_solleva_non_perde_l_ack(self):
        # Se l'eccezione uscisse da qui il comando resterebbe senza conferma e
        # la sessione slitterebbe di un report: il guasto che attendi_ack
        # esiste per evitare.
        def esplode(_):
            raise RuntimeError("boom")
        controlpad.OSSERVATORE = esplode
        dev = self.DevFinto([rapporto("5200000007"),
                             rapporto("5615000000000000")])
        risposta = controlpad.attendi_ack(dev, b"\x56\x15", timeout_ms=200)
        self.assertIsNotNone(risposta)
        self.assertEqual(risposta[:2], b"\x56\x15")


if __name__ == "__main__":
    unittest.main()


class OrdineModalitaTest(unittest.TestCase):
    """`hardware_mode_changed` porta un numero di slot, non un nome.

    L'app lo usa come indice: `Effects.modes[slot].id`. Se le due liste si
    scostassero — una modalita aggiunta da una parte sola, o due scambiate —
    la sincronia continuerebbe a funzionare mostrando la modalita sbagliata,
    e non fallirebbe niente da nessuna parte. Questo test e l'unico posto in
    cui le due liste si guardano in faccia.
    """

    SWIFT = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "ControlPadGUI", "Sources", "ControlPadGUI", "Models", "Effects.swift")

    def test_stesso_ordine_in_swift_e_in_python(self):
        import re
        if not os.path.exists(self.SWIFT):
            self.skipTest("sorgente Swift non presente")
        testo = open(self.SWIFT, encoding="utf-8").read()
        blocco = testo[testo.index("static let modes"):]
        blocco = blocco[:blocco.index("\n    ]")]
        swift = re.findall(r'\.init\(id: "([A-Za-z]+)"', blocco)
        self.assertEqual(swift, effects.SLOT_ORDER)


class StatoValidoTest(unittest.TestCase):
    """Il 255 del registro 51 28 non e una modalita.

    `51 28 00 00 ff` e il comando di applicazione, non una scelta di
    modalita, e dopo averlo mandato `52 28 00 00` rilegge 255. Riferirlo
    produceva un `hardware_mode_changed` con `slot: 255` che l'app scartava
    in silenzio, perche gli slot sono quattordici: la sincronia dell'effetto
    si fermava li senza che comparisse un errore.
    """

    def setUp(self):
        self.eventi = []
        self.evento_vero, self.log_vero = bridge._event, bridge._log
        bridge._event = lambda **campi: self.eventi.append(campi)
        bridge._log = lambda testo: None
        with bridge._stato_pad_lock:
            bridge._stato_pad.clear()

    def tearDown(self):
        bridge._event, bridge._log = self.evento_vero, self.log_vero
        with bridge._stato_pad_lock:
            bridge._stato_pad.clear()

    def test_modalita_255_non_e_uno_stato(self):
        self.assertFalse(bridge._stato_valido("modalita", 0xFF))

    def test_le_quattordici_modalita_sono_valide(self):
        for slot in range(len(effects.SLOT_ORDER)):
            self.assertTrue(bridge._stato_valido("modalita", slot), slot)
        self.assertFalse(bridge._stato_valido("modalita", len(effects.SLOT_ORDER)))

    def test_i_ventiquattro_banchi_sono_validi(self):
        for banco in range(24):
            self.assertTrue(bridge._stato_valido("banco", banco), banco)
        self.assertFalse(bridge._stato_valido("banco", 24))

    def test_l_applicazione_non_produce_un_evento(self):
        dev = InterrogaStatoTest.DevFinto(banco=3, modalita=7)
        bridge._interroga_stato(dev)          # riferimento: modo 7
        self.eventi.clear()
        dev.modalita = 0xFF                    # e passata un'applicazione
        bridge._interroga_stato(dev)
        self.assertEqual(self.eventi, [])
        # e la modalita nota resta quella vera, non il residuo
        self.assertEqual(bridge._stato_pad["modalita"], 7)

    def test_dopo_l_applicazione_una_modalita_vera_passa(self):
        dev = InterrogaStatoTest.DevFinto(banco=3, modalita=7)
        bridge._interroga_stato(dev)
        self.eventi.clear()
        dev.modalita = 0xFF
        bridge._interroga_stato(dev)
        dev.modalita = 2                       # l'utente preme "effetto -"
        bridge._interroga_stato(dev)
        self.assertEqual(self.eventi,
                         [{"event": "hardware_mode_changed", "slot": 2}])

    def test_annuncio_spontaneo_di_255_ignorato(self):
        bridge._interpreta_report(bytes(rapporto("52280000ff")))
        self.assertEqual(self.eventi, [])


class AnimazioneInterrogaTest(unittest.TestCase):
    """Chi tiene il device deve lasciar passare chi ha da chiedere.

    Su macOS un secondo `open_path` sullo stesso device fallisce, quindi
    mentre l'animazione degli indicatori gira il thread di ascolto non apre
    niente: nel diario compariva "ascolto in attesa, device occupato: open
    failed" subito dopo ogni `start_indicator_effect`. E l'app quell'
    animazione la tiene accesa quasi sempre, per i LED di profilo — quindi
    profilo ed effetto smettevano di seguire il pad *nell'uso normale*, non in
    un caso limite. L'interrogazione viaggia adesso sull'handle
    dell'animazione.
    """

    class PadFinto:
        def __init__(self):
            self.fotogrammi = 0

        def set_indicators(self, colori, commit=False, banco=None):
            self.fotogrammi += 1
            self.banco = banco

    def test_la_callback_viene_chiamata_fra_i_fotogrammi(self):
        import indicatori
        pad = self.PadFinto()
        ferma = threading.Event()
        visite = []

        def visita(p):
            visite.append(p)
            if len(visite) >= 3:
                ferma.set()

        n, _, _ = indicatori.riproduci_finche(
            pad, lambda t: [(0, 0, 0)] * 4, ferma, fps=200,
            fra_i_fotogrammi=visita, ogni=0.01)

        self.assertGreaterEqual(len(visite), 3)
        self.assertTrue(all(v is pad for v in visite),
                        "la callback deve ricevere l'handle dell'animazione")
        self.assertGreater(n, 0)

    def test_una_callback_che_solleva_non_ferma_l_animazione(self):
        import indicatori
        pad = self.PadFinto()
        ferma = threading.Event()
        chiamate = []

        def esplode(_):
            chiamate.append(1)
            if len(chiamate) >= 3:
                ferma.set()
            raise RuntimeError("boom")

        n, _, _ = indicatori.riproduci_finche(
            pad, lambda t: [(0, 0, 0)] * 4, ferma, fps=200,
            fra_i_fotogrammi=esplode, ogni=0.01)
        self.assertGreaterEqual(len(chiamate), 3)
        self.assertGreater(n, 0)

    def test_senza_callback_si_comporta_come_prima(self):
        import indicatori
        pad = self.PadFinto()
        ferma = threading.Event()
        threading.Timer(0.05, ferma.set).start()
        n, sec, _ = indicatori.riproduci_finche(
            pad, lambda t: [(0, 0, 0)] * 4, ferma, fps=200)
        self.assertGreater(n, 0)
        self.assertEqual(n, pad.fotogrammi)


class BancoDiDestinazioneTest(unittest.TestCase):
    """`write_session` deve scegliere il banco prima di scrivere.

    La sessione non porta con se il banco in cui deve finire: si scrive in
    quello attivo in quel momento. Misurato sul device — scritta una
    rimappatura col pad sul banco 5, `52 20 35 00` la rilegge solo dal banco
    5, e dai banchi 2 e 7 torna il valore di fabbrica. Senza la scelta
    esplicita, modificare un profilo qualunque nell'app scriveva sempre nello
    stesso banco: uno funzionava e gli altri ventitre no.
    """

    def setUp(self):
        self.chiamate = []
        self.veri = (bridge.ControlPad, bridge.session_scrivi, bridge._log,
                     bridge._ferma_polling, bridge._riprendi_polling,
                     bridge._ferma_animazione, bridge._chiudi_pad_persistente)

        prova = self

        class PadFinto:
            def __enter__(self): return self
            def __exit__(self, *e): return False
            def set_profile(self, n): prova.chiamate.append(("banco", n))

        bridge.ControlPad = PadFinto
        bridge.session_scrivi = lambda **kw: (
            self.chiamate.append(("scrivi", kw.get("remaps"))) or 0)
        self.verifica_vera = bridge._verifica_scrittura
        bridge._verifica_scrittura = lambda banco, remaps, macros=(): {}
        bridge._log = lambda t: None
        bridge._ferma_polling = lambda *a, **k: None
        bridge._riprendi_polling = lambda: None
        bridge._ferma_animazione = lambda: None
        bridge._chiudi_pad_persistente = lambda: None
        with bridge._stato_pad_lock:
            bridge._stato_pad.clear()

    def tearDown(self):
        (bridge.ControlPad, bridge.session_scrivi, bridge._log,
         bridge._ferma_polling, bridge._riprendi_polling,
         bridge._ferma_animazione, bridge._chiudi_pad_persistente) = self.veri
        bridge._verifica_scrittura = self.verifica_vera
        with bridge._stato_pad_lock:
            bridge._stato_pad.clear()

    def test_il_banco_si_sceglie_prima_di_scrivere(self):
        bridge.handle({"cmd": "write_session", "profile": 11,
                       "remaps": {"53": 62}})
        self.assertEqual(self.chiamate,
                         [("banco", 11), ("scrivi", {0x35: 62})])

    def test_senza_banco_si_scrive_dove_si_e(self):
        # Compatibilita: chi non lo manda ottiene il comportamento di prima.
        bridge.handle({"cmd": "write_session", "remaps": {"53": 62}})
        self.assertEqual(self.chiamate, [("scrivi", {0x35: 62})])

    def test_il_banco_scelto_non_torna_indietro_come_evento(self):
        # L'ha scelto l'app: rimandarglielo le farebbe ricaricare il profilo.
        bridge.handle({"cmd": "write_session", "profile": 6, "remaps": {}})
        self.assertEqual(bridge._stato_pad.get("banco"), 6)

    def test_banco_fuori_scala_rifiutato_prima_di_toccare_il_device(self):
        with self.assertRaises(ValueError):
            bridge.handle({"cmd": "write_session", "profile": 24})
        self.assertEqual(self.chiamate, [])


class VerificaScritturaTest(unittest.TestCase):
    """La scrittura si rilegge, non si deduce.

    Il device ACKa anche quello che non esegue — e il difetto ricorrente di
    questo protocollo — quindi `missing_acks: 0` non dice che la
    configurazione sia finita dove doveva. La rilettura lo dice.
    """

    class PadFinto:
        def __init__(self, banco, keymap):
            self.banco, self.keymap = banco, keymap

        def __enter__(self): return self
        def __exit__(self, *e): return False

        def _send(self, payload, label="", settle=0.005):
            payload = bytes(payload)
            if payload[:2] == b"\x52\x00":
                return b"\x52\x00\x00\x00" + bytes([self.banco]) + bytes(59)
            if payload[:2] == b"\x52\x20":
                azione = self.keymap.get(payload[2], 0x00FF)
                return (b"\x52\x20" + bytes([payload[2], 0])
                        + bytes([azione & 0xFF, azione >> 8]) + bytes(58))
            return None

    def setUp(self):
        self.vero_pad, self.vero_log = bridge.ControlPad, bridge._log
        self.righe = []
        bridge._log = self.righe.append

    def tearDown(self):
        bridge.ControlPad, bridge._log = self.vero_pad, self.vero_log

    def _con(self, banco, keymap):
        bridge.ControlPad = lambda: self.PadFinto(banco, keymap)

    def test_scrittura_riuscita(self):
        self._con(banco=4, keymap={0x35: 0x003E})
        esito = bridge._verifica_scrittura(4, {0x35: 0x003E})
        self.assertEqual(esito, {"profile_written": 4, "verified": True})

    def test_banco_sbagliato_lo_dice(self):
        # Il pad e finito altrove: la scrittura c'e ma non dove serviva.
        self._con(banco=1, keymap={0x35: 0x003E})
        esito = bridge._verifica_scrittura(4, {0x35: 0x003E})
        self.assertEqual(esito["profile_written"], 1)
        self.assertFalse(esito["verified"])
        self.assertTrue(any("chiesto il banco 4" in r for r in self.righe))

    def test_rimappatura_non_arrivata_lo_dice(self):
        self._con(banco=4, keymap={})          # il pad ha il valore di fabbrica
        esito = bridge._verifica_scrittura(4, {0x35: 0x003E})
        self.assertFalse(esito["verified"])
        self.assertTrue(any("0x35" in r for r in self.righe))

    def test_senza_banco_chiesto_verifica_solo_la_keymap(self):
        self._con(banco=9, keymap={0x35: 0x003E})
        esito = bridge._verifica_scrittura(None, {0x35: 0x003E})
        self.assertTrue(esito["verified"])
        self.assertEqual(esito["profile_written"], 9)

    def test_un_pad_che_non_risponde_non_fa_cadere_la_scrittura(self):
        def esplode():
            raise OSError("open failed")
        bridge.ControlPad = esplode
        esito = bridge._verifica_scrittura(4, {0x35: 0x003E})
        self.assertEqual(esito, {})
        self.assertTrue(any("verifica" in r for r in self.righe))


class VerificaMacroTest(unittest.TestCase):
    """Una sessione di sole macro deve essere verificata sulle macro.

    La prima versione guardava solo le rimappature, quindi una scrittura fatta
    di sole macro — il caso normale quando si assegna una macro a un tasto —
    passava con "0 rimappature rilette" senza che nessuno avesse controllato
    niente. `52 18 <slot> 00` risponde `<tasto> <tipo>`, con `ff 3f` a slot
    vuoto.
    """

    class PadFinto:
        def __init__(self, banco, slot):
            self.banco, self.slot = banco, slot

        def __enter__(self): return self
        def __exit__(self, *e): return False

        def _send(self, payload, label="", settle=0.005):
            payload = bytes(payload)
            if payload[:2] == b"\x52\x00":
                return b"\x52\x00\x00\x00" + bytes([self.banco]) + bytes(59)
            if payload[:2] == b"\x52\x18":
                tasto, tipo = self.slot.get(payload[2], (0xFF, 0x3F))
                return (b"\x52\x18" + bytes([payload[2], 0, tasto, tipo])
                        + bytes(58))
            return None

    def setUp(self):
        self.vero_pad, self.vero_log = bridge.ControlPad, bridge._log
        self.righe = []
        bridge._log = self.righe.append

    def tearDown(self):
        bridge.ControlPad, bridge._log = self.vero_pad, self.vero_log

    def test_macro_arrivata(self):
        bridge.ControlPad = lambda: self.PadFinto(3, {0: (0x35, 0x3C)})
        esito = bridge._verifica_scrittura(3, {}, [(0, 0x35, b"", "PROVA")])
        self.assertTrue(esito["verified"])

    def test_slot_rimasto_vuoto_lo_dice(self):
        bridge.ControlPad = lambda: self.PadFinto(3, {})
        esito = bridge._verifica_scrittura(3, {}, [(0, 0x35, b"", "PROVA")])
        self.assertFalse(esito["verified"])
        self.assertTrue(any("slot vuoto" in r for r in self.righe))

    def test_macro_finita_sul_tasto_sbagliato_lo_dice(self):
        bridge.ControlPad = lambda: self.PadFinto(3, {0: (0x1E, 0x3C)})
        esito = bridge._verifica_scrittura(3, {}, [(0, 0x35, b"", "PROVA")])
        self.assertFalse(esito["verified"])
        self.assertTrue(any("macro slot 0" in r for r in self.righe))

    def test_il_riepilogo_conta_le_macro(self):
        bridge.ControlPad = lambda: self.PadFinto(3, {0: (0x35, 0x3C)})
        bridge._verifica_scrittura(3, {}, [(0, 0x35, b"", "PROVA")])
        self.assertTrue(any("1 macro" in r for r in self.righe))


class IndirizzoIndicatoriTest(unittest.TestCase):
    """I quattro LED hanno uno slot per banco, non un registro solo.

    Il software ufficiale legge ventiquattro indirizzi da dodici byte a passo
    dodici — 0x00f0, 0x00fc, 0x0108 … 0x0204 — ogni volta che il banco attivo
    cambia. Il progetto ha usato a lungo il solo `0x00fc`, che e il **secondo**
    di quella serie: lo slot del banco 1, cioe del profilo che l'app chiama
    P2. Ogni scrittura degli indicatori finiva li qualunque banco fosse
    attivo, quindi i LED rispondevano su P2 e da nessun'altra parte — ed era
    esattamente il sintomo riferito. La rilettura non lo smascherava perche
    usava lo stesso indirizzo fisso della scrittura.
    """

    def test_la_serie_e_quella_letta_dal_software_ufficiale(self):
        osservati = [0x00F0, 0x00FC, 0x0108, 0x0114, 0x0120, 0x012C, 0x0138,
                     0x0144, 0x0150, 0x015C, 0x0168, 0x0174, 0x0180, 0x018C,
                     0x0198, 0x01A4, 0x01B0, 0x01BC, 0x01C8, 0x01D4, 0x01E0,
                     0x01EC, 0x01F8, 0x0204]
        self.assertEqual([controlpad.indicator_address(b) for b in range(24)],
                         osservati)

    def test_0x00fc_e_il_banco_1(self):
        # Il valore usato finora, e il motivo del "funziona solo P2".
        self.assertEqual(controlpad.indicator_address(1), 0x00FC)

    def test_banco_fuori_scala_rifiutato(self):
        for banco in (-1, 24, 100):
            with self.assertRaises(ValueError):
                controlpad.indicator_address(banco)

    def test_il_comando_porta_l_indirizzo_in_little_endian(self):
        self.assertEqual(controlpad._indicator_cmd(0x50, 3).hex(),
                         "5550" + "1401" + "0c")
        self.assertEqual(controlpad._indicator_cmd(0x40, 23).hex(),
                         "5540" + "0402" + "0c")

    def test_la_sessione_scrive_nello_slot_del_banco_chiesto(self):
        import session
        gruppo = session._gruppo_indicatori([(1, 2, 3)] * 4, banco=5)
        scrittura = next(p for p, _ in gruppo if p[:2] == b"\x55\x50")
        atteso = controlpad.indicator_address(5)
        self.assertEqual(int.from_bytes(scrittura[2:4], "little"), atteso)
        self.assertEqual(scrittura[4], 0x0C)


class TastiProfiloTest(unittest.TestCase):
    """Scorrere i profili non e un codice azione: e una rimozione da 51 94.

    Il campo azione di `51 20` non ha un codice per questa funzione — non
    compare in nessuna delle venti catture. Un tasto diventa un tasto profilo
    venendo tolto dalla tabella `51 94`, con lo slot a `ff ff ff ff`, e nella
    keymap conserva `00ff`. `PROFILO_AVANTI` / `PROFILO_INDIETRO` sono quindi
    convenzioni interne all'app, che `costruisci` traduce e non scrive mai sul
    dispositivo.
    """

    def setUp(self):
        import session
        self.session = session
        # 'z' e 'Ctrl', gli stessi della cattura: indici per colonne 8 e 4.
        self.z, self.ctrl = 0x1D, 0xE0

    def _reports(self, **kw):
        return [p for p, _ in self.session.costruisci(**kw)]

    def _keymap(self, reports, tasto):
        for p in reports:
            if p[:2] == b"\x51\x20" and p[2] == tasto:
                return p[4] | (p[5] << 8)
        return None

    def _slot_94(self, reports, indice):
        for p in reports:
            if p[:2] != b"\x51\x94":
                continue
            corpo = p[4:]
            for o in range(0, len(corpo) - 3, 4):
                if int.from_bytes(corpo[o + 2:o + 4], "little") == indice:
                    return corpo[o:o + 4]
        return None

    def test_il_tasto_sparisce_da_51_94(self):
        r = self._reports(remaps={self.z: self.session.PROFILO_AVANTI})
        self.assertIsNone(self._slot_94(r, 8),
                          "lo slot del tasto non deve piu comparire come voce")
        # e al suo posto c'e il riempimento
        pieni = [p for p in r if p[:2] == b"\x51\x94"]
        self.assertTrue(any(b"\xff\xff\xff\xff" in p for p in pieni))

    def test_il_codice_interno_non_finisce_nella_keymap(self):
        r = self._reports(remaps={self.z: self.session.PROFILO_AVANTI})
        self.assertEqual(self._keymap(r, self.z), self.session.NESSUNA_RIMAPPATURA)
        for p in r:
            if p[:2] == b"\x51\x20":
                azione = p[4] | (p[5] << 8)
                self.assertNotIn(azione, (self.session.PROFILO_AVANTI,
                                          self.session.PROFILO_INDIETRO))

    def test_i_due_versi_si_distinguono_nella_tabella_51_90(self):
        # Verso ricavato dall'uso: chi torna indietro porta 0, chi avanza
        # conserva l'identita. Vedi la nota in session._tabella_profili.
        r = self._reports(remaps={self.ctrl: self.session.PROFILO_AVANTI,
                                  self.z: self.session.PROFILO_INDIETRO})
        tab = next(p[4:28] for p in r if p[:2] == b"\x51\x90")
        self.assertEqual(tab[4], 4, "il tasto 'avanti' conserva l'identita")
        self.assertEqual(tab[8], 0, "quello 'indietro' porta 0 al suo indice")

    def test_qualunque_tasto_puo_fare_da_selettore(self):
        # E il punto della funzione: non i due tasti della cattura, ma quelli
        # che sceglie l'utente.
        for tasto, indice in ((0x35, 0), (0x21, 20), (0x2C, 19)):
            r = self._reports(remaps={tasto: self.session.PROFILO_AVANTI})
            self.assertIsNone(self._slot_94(r, indice), f"tasto 0x{tasto:02x}")

    def test_senza_tasti_profilo_la_tabella_resta_intatta(self):
        r = self._reports()
        for indice in (0, 4, 8, 23):
            self.assertIsNotNone(self._slot_94(r, indice))

    def test_convivono_con_seleziona_profilo(self):
        r = self._reports(remaps={self.z: self.session.PROFILO_INDIETRO},
                          profile_keys={0: 7})
        tab = next(p[4:28] for p in r if p[:2] == b"\x51\x90")
        self.assertEqual(tab[0], 7)      # il selettore assoluto
        self.assertEqual(tab[8], 0)      # il tasto "indietro"


class VerificaTastiProfiloTest(unittest.TestCase):
    """I codici interni non vanno cercati nella keymap del dispositivo.

    `PROFILO_AVANTI` / `PROFILO_INDIETRO` sono convenzioni dell'app: sul pad
    quei tasti portano `00ff`, e la funzione sta nella loro assenza da `51 94`.
    La prima versione della verifica li cercava fra le rimappature e falliva su
    una scrittura riuscita — nel diario "chiesto 0x0111, riletto 0x00ff" — e
    `Commands.swift`, che di `verified == false` fa un errore, lo mostrava
    all'utente a ogni salvataggio che contenesse un tasto profilo.
    """

    class PadFinto:
        def __enter__(self): return self
        def __exit__(self, *e): return False

        def _send(self, payload, label="", settle=0.005):
            payload = bytes(payload)
            if payload[:2] == b"\x52\x00":
                return b"\x52\x00\x00\x00" + bytes([3]) + bytes(59)
            if payload[:2] == b"\x52\x20":
                # Il pad risponde 00ff: e il valore giusto per un tasto profilo.
                return b"\x52\x20" + bytes([payload[2], 0, 0xFF, 0x00]) + bytes(58)
            return None

    def setUp(self):
        self.vero_pad, self.vero_log = bridge.ControlPad, bridge._log
        self.righe = []
        bridge._log = self.righe.append
        bridge.ControlPad = lambda: self.PadFinto()

    def tearDown(self):
        bridge.ControlPad, bridge._log = self.vero_pad, self.vero_log

    def test_un_tasto_profilo_non_fa_fallire_la_verifica(self):
        import session
        esito = bridge._verifica_scrittura(
            3, {0x1D: session.PROFILO_AVANTI, 0xE0: session.PROFILO_INDIETRO})
        self.assertTrue(esito["verified"], self.righe)

    def test_una_rimappatura_vera_resta_verificata(self):
        import session
        esito = bridge._verifica_scrittura(
            3, {0x1D: session.PROFILO_AVANTI, 0x35: 0x003E})
        self.assertFalse(esito["verified"])
        self.assertTrue(any("0x35" in r for r in self.righe))
        self.assertFalse(any("0x1d" in r for r in self.righe),
                         "il tasto profilo non deve comparire fra i problemi")


class RipristinoAllUscitaTest(unittest.TestCase):
    """Alla chiusura il device va chiesto a tutti e tre quelli che lo tengono.

    L'animazione, l'ascolto e l'handle persistente aprono ciascuno il proprio,
    e su macOS il secondo `open_path` fallisce. Fermando la sola animazione —
    com'era — il ripristino dei colori fissi finiva sempre in "open failed", e
    i LED restavano sull'ultimo fotogramma dell'animazione invece di tornare ai
    colori scelti. Si vedeva a ogni chiusura dell'app.
    """

    def setUp(self):
        self.veri = (bridge._ferma_animazione, bridge._ferma_polling,
                     bridge._chiudi_pad_persistente, bridge._device_present,
                     bridge.ControlPad, bridge._log, bridge._colori_fissi)
        self.mollati = []
        bridge._ferma_animazione = lambda: self.mollati.append("animazione")
        bridge._ferma_polling = lambda *a, **k: self.mollati.append("ascolto")
        bridge._chiudi_pad_persistente = lambda: self.mollati.append("persistente")
        bridge._device_present = lambda: True
        bridge._log = lambda t: None
        bridge._colori_fissi = [(1, 2, 3)] * 4

    def tearDown(self):
        (bridge._ferma_animazione, bridge._ferma_polling,
         bridge._chiudi_pad_persistente, bridge._device_present,
         bridge.ControlPad, bridge._log, bridge._colori_fissi) = self.veri

    def test_molla_tutti_e_tre_prima_di_aprire(self):
        aperto = []

        class Pad:
            def __enter__(self): return self
            def __exit__(self, *e): return False
            def set_indicators(self, colori, commit=False, banco=None):
                aperto.append((tuple(colori), banco))

        bridge.ControlPad = Pad
        bridge._ripristina_fissi()
        self.assertEqual(set(self.mollati), {"animazione", "ascolto", "persistente"})
        self.assertEqual(len(aperto), 1)

    def test_riprova_se_il_device_e_ancora_occupato(self):
        # Su macOS il rilascio non e immediato: chiudere e riaprire subito puo
        # trovarlo ancora preso.
        tentativi = []

        class PadRestio:
            def __enter__(self):
                tentativi.append(1)
                if len(tentativi) < 3:
                    raise OSError("open failed")
                return self

            def __exit__(self, *e): return False
            def set_indicators(self, colori, commit=False, banco=None): pass

        bridge.ControlPad = PadRestio
        bridge._ripristina_fissi()
        self.assertEqual(len(tentativi), 3, "deve riprovare finche riesce")

    def test_un_device_che_non_si_apre_mai_non_fa_cadere_l_uscita(self):
        class PadMorto:
            def __enter__(self): raise OSError("open failed")
            def __exit__(self, *e): return False

        bridge.ControlPad = PadMorto
        bridge._ripristina_fissi()          # non deve sollevare
