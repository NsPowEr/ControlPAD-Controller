"""La regola degli ACK, provata contro un device finto.

Il pad intercala report non richiesti fra un comando e la sua conferma. Chi
legge una volta sola slitta di uno, poi di due, e da li il device continua ad
ACKare e smette di eseguire: sintomo sleale, perche ogni indicatore software
dice che e andato tutto bene. Qui il device finto si comporta cosi apposta.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from controlpad import attendi_ack                                  # noqa: E402


class DeviceFinto:
    """Risponde a ogni write con l'eco dell'header, preceduta da un po' di
    rumore: `ff aa` (stato di tasti e rotelle) e un `42 20` occasionale."""

    def __init__(self, rumore_per_comando=2, muto=False):
        self.rumore = rumore_per_comando
        self.muto = muto
        self.coda = []
        self.scritti = []

    def write(self, payload):
        self.scritti.append(bytes(payload[1:]))          # via il report id
        self.coda.extend([bytes.fromhex("ffaa") + bytes(62)] * self.rumore)
        if not self.muto:
            self.coda.append(bytes(payload[1:3]) + bytes(62))
        return len(payload)

    def read(self, size, timeout_ms=0):
        return list(self.coda.pop(0)) if self.coda else []


class Drenaggio(unittest.TestCase):
    def test_scarta_il_rumore_e_trova_la_sua_eco(self):
        dev = DeviceFinto(rumore_per_comando=3)
        dev.write(bytes([0x00, 0x41, 0x80]) + bytes(62))
        reply = attendi_ack(dev, b"\x41\x80")
        self.assertIsNotNone(reply)
        self.assertEqual(reply[:2], b"\x41\x80")
        self.assertEqual(dev.coda, [])                   # coda svuotata

    def test_senza_drenaggio_le_letture_slitterebbero(self):
        # Una lettura sola per comando: al secondo comando quello che torna e
        # ancora il rumore del primo. E' il difetto che questo test difende.
        dev = DeviceFinto(rumore_per_comando=1)
        dev.write(bytes([0x00, 0x41, 0x80]) + bytes(62))
        primo = dev.read(64)
        self.assertEqual(bytes(primo[:2]), b"\xff\xaa")

    def test_la_coda_non_si_accumula_su_una_sequenza_lunga(self):
        dev = DeviceFinto(rumore_per_comando=2)
        for _ in range(150):
            dev.write(bytes([0x00, 0x51, 0x20]) + bytes(62))
            self.assertIsNotNone(attendi_ack(dev, b"\x51\x20"))
        self.assertEqual(dev.coda, [])

    def test_un_comando_senza_eco_scade_invece_di_bloccare(self):
        dev = DeviceFinto(rumore_per_comando=1, muto=True)
        dev.write(bytes([0x00, 0x41, 0x80]) + bytes(62))
        self.assertIsNone(attendi_ack(dev, b"\x41\x80", timeout_ms=20))

    def test_la_risposta_di_una_rilettura_torna_intera(self):
        # 55 40 porta i dodici byte dei LED indicatori dentro la sua eco.
        dev = DeviceFinto(rumore_per_comando=1)
        dev.coda.append(bytes.fromhex("5540fc000c") + bytes(range(12)) + bytes(47))
        reply = attendi_ack(dev, b"\x55\x40")
        self.assertEqual(reply[5:17], bytes(range(12)))


class InviaSessione(unittest.TestCase):
    """session.invia deve usare la stessa regola: e il percorso piu lungo del
    progetto, oltre centocinquanta report, quindi quello dove la deriva pesa
    di piu."""

    def invia_con(self, dev):
        import session
        from unittest import mock
        reports = session.costruisci()
        with mock.patch.object(session.hid, "enumerate",
                               return_value=[{"path": b"finto",
                                              "usage_page": 0xFF00}]), \
             mock.patch.object(session.hid, "device", return_value=dev), \
             mock.patch.object(session.time, "sleep", lambda _: None):
            dev.open_path = lambda _p: None
            dev.close = lambda: None
            return reports, session.invia(reports, timeout_ms=5)

    def test_ogni_report_riceve_la_sua_conferma(self):
        dev = DeviceFinto(rumore_per_comando=2)
        reports, senza_ack = self.invia_con(dev)
        self.assertEqual(senza_ack, 0)
        self.assertEqual(len(dev.scritti), len(reports))
        self.assertEqual(dev.coda, [])

    def test_un_device_che_non_risponde_viene_contato(self):
        dev = DeviceFinto(rumore_per_comando=0, muto=True)
        reports, senza_ack = self.invia_con(dev)
        self.assertEqual(senza_ack, len(reports))


if __name__ == "__main__":
    unittest.main()
