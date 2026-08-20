"""Codifica delle macro e costruzione dei comandi di illuminazione.

Sono le due parti in cui un byte fuori posto non da errore: il device ACKa e
non esegue. Qui si controllano contro i valori letti nelle catture, che sono
l'unica verita disponibile senza il pad collegato.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import effects                                                      # noqa: E402
from macro import (LSHIFT, PRESS, RELEASE, TERMINATOR, EventList,
                   events_for, events_for_combo, macro_packets, sanitize_name)


def eventi(body):
    """Il corpo macro spezzato in quartine, terminatore escluso."""
    self_body = body[:-len(TERMINATOR)]
    return [self_body[i:i + 4] for i in range(0, len(self_body), 4)]


class CodificaTesto(unittest.TestCase):
    def test_finisce_sempre_col_terminatore(self):
        self.assertTrue(events_for("ciao").endswith(TERMINATOR))

    def test_una_minuscola_sono_due_eventi(self):
        self.assertEqual(len(eventi(events_for("a"))), 2)

    def test_shift_resta_giu_per_tutto_il_gruppo_di_maiuscole(self):
        # "CIAo": shift scende una volta, risale davanti alla minuscola.
        quartine = eventi(events_for("CIAo"))
        premute = [q for q in quartine if q[0] == LSHIFT and q[1] == PRESS]
        rilasci = [q for q in quartine if q[0] == LSHIFT and q[1] == RELEASE]
        self.assertEqual(len(premute), 1)
        self.assertEqual(len(rilasci), 1)
        self.assertLess(quartine.index(premute[0]), quartine.index(rilasci[0]))

    def test_lo_shift_aperto_in_fondo_viene_chiuso(self):
        quartine = eventi(events_for("AB"))
        self.assertEqual(quartine[-1][0], LSHIFT)
        self.assertEqual(quartine[-1][1], RELEASE)

    def test_la_macro_di_esempio_di_PROTOCOL_torna_uguale(self):
        # PROTOCOL.md, "Formato di una macro": Shift giu, 'a', su, Shift su.
        quartine = eventi(events_for("A"))
        self.assertEqual([(q[0], q[1]) for q in quartine],
                         [(LSHIFT, PRESS), (0x04, PRESS),
                          (0x04, RELEASE), (LSHIFT, RELEASE)])

    def test_il_ritardo_e_little_endian_a_16_bit(self):
        ev = EventList()
        ev.press(0x04, 1174)
        self.assertEqual(ev.buf[2:4], bytes([1174 & 0xFF, 1174 >> 8]))

    def test_un_carattere_non_mappato_e_un_errore_esplicito(self):
        with self.assertRaises(ValueError):
            events_for("cioè")

    def test_il_layout_italiano_della_barra_verticale(self):
        # '|' e Shift + il tasto a sinistra dell'1, non Shift-0x31.
        quartine = eventi(events_for("|"))
        self.assertEqual([q[0] for q in quartine],
                         [LSHIFT, 0x35, 0x35, LSHIFT])


class CodificaCombinazione(unittest.TestCase):
    def test_i_modificatori_sono_ancora_giu_quando_arriva_il_tasto(self):
        quartine = eventi(events_for_combo([0xE0, 0xE2, 0x4C]))
        tipi = [q[1] for q in quartine]
        self.assertEqual(tipi, [PRESS, PRESS, PRESS, RELEASE, RELEASE, RELEASE])

    def test_si_rilascia_in_ordine_inverso(self):
        quartine = eventi(events_for_combo([0xE0, 0xE2, 0x4C]))
        self.assertEqual([q[0] for q in quartine[3:]], [0x4C, 0xE2, 0xE0])


class Spezzatura(unittest.TestCase):
    """Quindici eventi sono la capienza di *un* report: oltre serve il byte di
    continuazione, che con due soli report non era distinguibile da un indice."""

    def test_quindici_eventi_stanno_in_un_report(self):
        body = b"\x04\x3c\x00\x00" * 14 + TERMINATOR
        pacchetti = macro_packets(body)
        self.assertEqual(len(pacchetti), 1)
        self.assertEqual(pacchetti[0][1], 0x00)
        self.assertEqual(pacchetti[0][2], 15)

    def test_il_primo_report_apre_e_gli_altri_continuano(self):
        body = b"\x04\x3c\x00\x00" * 48 + TERMINATOR
        pacchetti = macro_packets(body)
        self.assertEqual(len(pacchetti), 4)          # 49 eventi su 4 report
        self.assertEqual([p[1] for p in pacchetti], [0, 1, 1, 1])

    def test_il_terzo_byte_conta_gli_eventi_di_questo_report(self):
        body = b"\x04\x3c\x00\x00" * 48 + TERMINATOR
        pacchetti = macro_packets(body)
        self.assertEqual([p[2] for p in pacchetti], [15, 15, 15, 4])
        self.assertEqual(sum(p[2] for p in pacchetti), 49)

    def test_nessun_report_supera_i_64_byte(self):
        body = b"\x04\x3c\x00\x00" * 100 + TERMINATOR
        for p in macro_packets(body):
            self.assertLessEqual(len(p), 64)

    def test_il_corpo_rimesso_in_fila_e_quello_di_partenza(self):
        body = events_for("una frase lunga da spezzare su piu report")
        self.assertEqual(b"".join(p[4:] for p in macro_packets(body)), body)


class Modalita(unittest.TestCase):
    def test_il_colore_finisce_all_offset_dichiarato(self):
        for modo in effects.MODES:
            _, cmd = effects.build(modo.key, color1=[0x11, 0x22, 0x33, 0x44])
            self.assertEqual(cmd[modo.color1:modo.color1 + 4],
                             bytes([0x11, 0x22, 0x33, 0x44]), modo.key)

    def test_le_modalita_reattive_hanno_davvero_due_colori(self):
        doppie = [m for m in effects.MODES if m.color2 is not None]
        self.assertEqual(len(doppie), 6)
        for modo in doppie:
            _, cmd = effects.build(modo.key, color1=[1, 2, 3, 4],
                                   color2=[5, 6, 7, 8])
            self.assertEqual(cmd[modo.color2:modo.color2 + 4], bytes([5, 6, 7, 8]))

    def test_la_velocita_finisce_al_suo_byte(self):
        for modo in effects.MODES:
            _, cmd = effects.build(modo.key, speed=0x0B)
            if modo.speed < len(cmd):
                self.assertEqual(cmd[modo.speed], 0x0B, modo.key)

    def test_quello_che_non_si_passa_resta_come_nella_cattura(self):
        _, cmd = effects.build("static")
        self.assertEqual(cmd, effects.BY_KEY["static"].command)

    def test_quattordici_slot_sette_comandi_singoli_sei_doppi_e_personalizza(self):
        self.assertEqual(len(effects.SLOT_ORDER), 14)
        self.assertEqual(sum(1 for m in effects.MODES if m.color2 is None), 7)
        self.assertEqual(sum(1 for m in effects.MODES if m.color2 is not None), 6)

    def test_personalizza_non_e_un_comando_ma_uno_slot(self):
        # Non passa da set_mode: e la tabella per-tasto. Deve dirlo, non
        # cadere con un KeyError che l'app mostrerebbe cosi com'e.
        self.assertIn("custom", effects.SLOT_ORDER)
        self.assertNotIn("custom", effects.BY_KEY)
        with self.assertRaises(ValueError):
            effects.build("custom")

    def test_una_modalita_inesistente_e_un_errore_leggibile(self):
        with self.assertRaises(ValueError):
            effects.build("modalita che non esiste")

    def test_ogni_slot_tranne_personalizza_ha_il_suo_comando(self):
        for chiave in effects.SLOT_ORDER:
            if chiave == "custom":
                continue
            self.assertIn(chiave, effects.BY_KEY, chiave)

class SanitizzazioneNomi(unittest.TestCase):
    def test_nome_corto_viene_paddato_con_zeri(self):
        self.assertEqual(sanitize_name("abc"), b"abc" + b"\x00" * 9)

    def test_nome_esatto_dodici_byte(self):
        self.assertEqual(sanitize_name("abcdefghijkl"), b"abcdefghijkl")

    def test_nome_lungo_viene_troncato_a_dodici(self):
        result = sanitize_name("abcdefghijklmno")
        self.assertEqual(len(result), 12)
        self.assertEqual(result, b"abcdefghijkl")

    def test_nome_vuoto(self):
        self.assertEqual(sanitize_name(""), b"\x00" * 12)

    def test_caratteri_utf8_multibyte_non_spezzati(self):
        # 'è' e 2 byte in UTF-8: con 11 byte ASCII + è si sfora, e il
        # troncamento deve togliere l'intero codepoint invece di spezzarlo.
        result = sanitize_name("abcdefghijkè")
        self.assertEqual(len(result), 12)
        try:
            result.rstrip(b'\x00').decode('utf-8')
        except UnicodeDecodeError:
            self.fail("il nome troncato non e UTF-8 valido")

    def test_max_bytes_personalizzabile(self):
        self.assertEqual(len(sanitize_name("test", max_bytes=8)), 8)


class NormalizzazioneVelocita(unittest.TestCase):
    def test_valore_nel_range_1_10_viene_convertito(self):
        result = effects.normalize_speed(5)
        self.assertIsInstance(result, int)
        self.assertGreater(result, 0)

    def test_valore_grezzo_oltre_10_passa_invariato(self):
        self.assertEqual(effects.normalize_speed(15), 15)

    def test_none_resta_none(self):
        self.assertIsNone(effects.normalize_speed(None))

    def test_tipo2_usa_scala_diversa(self):
        t1 = effects.normalize_speed(5, key="static")
        t2 = effects.normalize_speed(5, key="crosshair")
        self.assertNotEqual(t1, t2)

    def test_estremi_non_escono_dal_range(self):
        self.assertEqual(effects.normalize_speed(0), effects._SPEED_T1[0])
        self.assertEqual(effects.normalize_speed(10), effects._SPEED_T1[-1])


if __name__ == "__main__":
    unittest.main()
