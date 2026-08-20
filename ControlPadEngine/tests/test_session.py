"""Quello che si puo verificare della sessione senza avere il pad in mano.

`costruisci()` e una funzione pura: prende la sessione registrata e restituisce
i report da inviare. Ogni bug trovato finora in questo file era visibile qui,
guardando i byte in uscita — e nessuno lo era guardando il codice.

    python3 -m unittest discover -s ControlPadEngine/tests
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import effects                                          # noqa: E402
import session                                          # noqa: E402
from layout import GRIGLIA, tutti_i_tasti               # noqa: E402
from macro import events_for                            # noqa: E402
from skeleton import SESSIONE                           # noqa: E402

NESSUNA = 0x00FF

LUCE = {"color1": [0x11, 0x22, 0x33, 0xFF], "color2": [0x44, 0x55, 0x66, 0xFF],
        "speed": 5, "mode": "static", "perkey": [(1, 2, 3)] * 25}


def keymap(reports):
    """{codice tasto: azione a 16 bit} come esce dai report 51 20."""
    return {p[2]: p[4] | (p[5] << 8) for p, _ in reports if p[:2] == b"\x51\x20"}


def primo(reports, prefisso):
    for p, _ in reports:
        if p.startswith(bytes.fromhex(prefisso)):
            return p
    return None


class KeymapSenzaEredita(unittest.TestCase):
    """La sessione registrata porta la configurazione di chi ha fatto la
    cattura: dieci tasti con un'azione non di fabbrica. Un tasto che l'utente
    non ha toccato non deve uscire con quei valori — e nemmeno con 0x00FF,
    vedi session._azione_predefinita."""

    def test_skeleton_contiene_davvero_le_rimappature_della_cattura(self):
        # Se un giorno lo skeleton venisse rigenerato pulito, questo test cade
        # e dice che il resto del file sta difendendo da un problema che non
        # c'e piu.
        sporchi = {p[2] for h, _ in SESSIONE
                   for p in [bytes.fromhex(h)]
                   if p[:2] == b"\x51\x20" and (p[4] | (p[5] << 8)) != NESSUNA}
        self.assertTrue(sporchi & {0x1F, 0x15, 0x09, 0x1B, 0x06, 0x19})

    def test_senza_remaps_ogni_tasto_batte_il_proprio_carattere(self):
        # Provato sul dispositivo: con 0x00FF i tasti n.1 (0x35) e n.17 (0x1D)
        # facevano girare il ciclo dei colori invece di battere il loro
        # carattere. Il codice va scritto esplicito.
        km = keymap(session.costruisci())
        for codice in tutti_i_tasti():
            if codice == session.TASTO_EFFETTI:
                continue
            self.assertEqual(km[codice], codice,
                             f"tasto 0x{codice:02x} non batte se stesso")

    def test_nessun_tasto_esce_a_0x00ff(self):
        km = keymap(session.costruisci())
        self.assertNotIn(NESSUNA, km.values())

    def test_il_tasto_senza_carattere_fa_girare_gli_effetti(self):
        # Il n.22 (0xC0) e l'unico dei ventiquattro senza un carattere da
        # battere, e nelle catture porta 0x0181.
        km = keymap(session.costruisci())
        self.assertEqual(km[session.TASTO_EFFETTI], session.FUNZIONI["effetto_avanti"])

    def test_solo_un_tasto_fa_girare_gli_effetti(self):
        km = keymap(session.costruisci())
        effetti = [k for k, azione in km.items()
                   if azione in (session.FUNZIONI["effetto_avanti"],
                                 session.FUNZIONI["effetto_indietro"])]
        self.assertEqual(effetti, [session.TASTO_EFFETTI])

    def test_chiedere_il_default_esplicito_da_lo_stesso_risultato(self):
        # "Comportamento di fabbrica" scelto dall'interfaccia non deve
        # rimettere 0x00FF, o si ricasca nel ciclo colori sui due tasti.
        km = keymap(session.costruisci(remaps={0x35: NESSUNA, 0x1D: NESSUNA}))
        self.assertEqual(km[0x35], 0x35)
        self.assertEqual(km[0x1D], 0x1D)

    def test_i_tasti_muti_della_cattura_non_restano_muti(self):
        # x, c, v e Alt portavano le macro della cattura, quindi avevano azione
        # 0x0000: scritti cosi su un pad dove quelle macro non ci sono piu, il
        # tasto non fa piu niente.
        km = keymap(session.costruisci())
        for codice in (0x1B, 0x06, 0x19, 0xE2):
            self.assertNotEqual(km[codice], 0x0000)

    def test_le_rotelle_restano_alle_funzioni_di_fabbrica(self):
        km = keymap(session.costruisci())
        self.assertEqual(km[0xC6], 0x0192)
        self.assertEqual(km[0xC7], 0x0193)
        self.assertEqual(km[0xF5], 0x00F5)
        self.assertEqual(km[0xF6], 0x00F6)

    def test_la_rimappatura_chiesta_passa(self):
        km = keymap(session.costruisci(remaps={0x14: 0x3E}))
        self.assertEqual(km[0x14], 0x3E)
        self.assertEqual(km[0x1A], 0x1A)         # il vicino resta com'era

    def test_una_rotella_riassegnata_vince_sul_valore_di_fabbrica(self):
        km = keymap(session.costruisci(remaps={0xC6: 0x00F0}))
        self.assertEqual(km[0xC6], 0x00F0)
        self.assertEqual(km[0xC7], 0x0193)

    def test_il_tasto_con_la_macro_non_batte_anche_il_suo_carattere(self):
        macros = [(8, 0x35, events_for("ciao"), "m")]
        km = keymap(session.costruisci(macros=macros))
        self.assertEqual(km[0x35], 0x0000)

    def test_un_tasto_selettore_e_marcato_nella_keymap(self):
        # indice per colonne 0 = riga 1, colonna 1 = il tasto `
        km = keymap(session.costruisci(profile_keys={0: 2}))
        self.assertEqual(km[0x35], session.FUNZIONI["seleziona_profilo"])


class SlotDellaModalita(unittest.TestCase):
    """I due punti che decidono con cosa il pad si riaccende. Il ciclo delle
    macro sovrascriveva la variabile che li porta, quindi con una macro nello
    slot 8 il pad si riaccendeva sulla modalita 8 (Lampeggio)."""

    def slot_scritti(self, macros):
        reports = session.costruisci(macros=macros, lighting=LUCE)
        stato = primo(reports, session.STATO_ILLUMINAZIONE)
        selezione = primo(reports, session.SELEZIONE_MODALITA)
        return stato[6], selezione[4]

    def test_senza_macro(self):
        stato, selezione = self.slot_scritti([])
        self.assertEqual(stato, 0)               # "static" e lo slot 0
        self.assertEqual(selezione, 0)

    def test_con_una_macro_in_uno_slot_alto(self):
        macros = [(8, 0x35, events_for("ciao"), "m")]
        stato, selezione = self.slot_scritti(macros)
        self.assertEqual(stato, 0)
        self.assertEqual(selezione, 0)

    def test_con_piu_macro(self):
        macros = [(8, 0x35, events_for("a"), "a"),
                  (9, 0x1E, events_for("b"), "b"),
                  (10, 0x1F, events_for("c"), "c")]
        stato, selezione = self.slot_scritti(macros)
        self.assertEqual(stato, 0)
        self.assertEqual(selezione, 0)

    def test_ogni_modalita_finisce_nel_suo_slot(self):
        for atteso, chiave in enumerate(effects.SLOT_ORDER):
            luce = dict(LUCE, mode=chiave)
            reports = session.costruisci(lighting=luce)
            self.assertEqual(primo(reports, session.SELEZIONE_MODALITA)[4],
                             atteso, f"modalita {chiave}")

    def test_velocita_nello_stato_persistente(self):
        reports = session.costruisci(lighting=dict(LUCE, speed=7))
        self.assertEqual(primo(reports, session.STATO_ILLUMINAZIONE)[7], 7)


class FormaDeiReport(unittest.TestCase):
    """Vincoli che il device non perdona e che nessun ACK segnala."""

    def test_nessun_report_supera_i_64_byte(self):
        macros = [(8, 0x35, events_for("frase abbastanza lunga da spezzarsi"), "m")]
        for payload, _ in session.costruisci(macros=macros, lighting=LUCE,
                                             profile_keys={0: 1},
                                             indicators=[(1, 2, 3)] * 4):
            self.assertLessEqual(len(payload), 64, payload.hex())

    def test_dopo_ogni_corpo_macro_c_e_la_pausa_di_flash(self):
        # Senza, il comando viene accettato con ACK regolare e non salva nulla.
        reports = session.costruisci(macros=[(8, 0x35, events_for("ciao"), "m")])
        corpi = [(p, gap) for p, gap in reports if p[0] == 0x53]
        self.assertTrue(corpi)
        for _, gap in corpi:
            self.assertGreaterEqual(gap, 0.072)

    def test_la_tabella_profili_esce_una_volta_sola(self):
        reports = session.costruisci(profile_keys={0: 1, 6: 2})
        tabelle = [p for p, _ in reports if p[:2] == b"\x51\x90"]
        self.assertEqual(len(tabelle), 1)
        self.assertEqual(tabelle[0][4 + 0], 1)
        self.assertEqual(tabelle[0][4 + 6], 2)

    def test_gli_indicatori_escono_una_volta_sola(self):
        colori = [(10, 20, 30), (40, 50, 60), (70, 80, 90), (100, 110, 120)]
        reports = session.costruisci(indicators=colori)
        scritture = [p for p, _ in reports if p.startswith(bytes.fromhex("5550fc000c"))]
        self.assertEqual(len(scritture), 1)
        self.assertEqual(scritture[0][5:17], bytes(b for c in colori for b in c))

    def test_i_gruppi_macro_della_cattura_spariscono(self):
        # Senza macro proprie non deve restarne nessuna di quelle registrate.
        reports = session.costruisci()
        self.assertEqual([p for p, _ in reports if p[0] == 0x53], [])
        assegnazioni = [p for p, _ in reports
                        if p[:2] == b"\x51\x18" and p[4:6] != b"\xff\x3f"]
        self.assertEqual(assegnazioni, [])

    def test_gli_slot_macro_sono_comunque_azzerati_tutti(self):
        azzeramenti = [p for p, _ in session.costruisci()
                       if p[:2] == b"\x51\x18" and p[4:6] == b"\xff\x3f"]
        self.assertEqual(len(azzeramenti), 24)


class Illuminazione(unittest.TestCase):
    def test_il_colore_finisce_in_ogni_slot_del_blob(self):
        reports = session.costruisci(lighting=LUCE)
        flusso = b"".join(p[4:4 + session.CHUNK_DATI]
                          for p, _ in reports if p[:2] == b"\x56\x21")
        self.assertIn(bytes(LUCE["color1"]), flusso)

    def test_i_colori_per_tasto_finiscono_nello_slot_personalizza(self):
        perkey = [(i, i, i) for i in range(1, 26)]
        reports = session.costruisci(lighting=dict(LUCE, mode="custom",
                                                   perkey=perkey))
        flusso = b"".join(p[4:4 + session.CHUNK_DATI]
                          for p, _ in reports if p[:2] == b"\x56\x21")
        self.assertIn(bytes(b for c in perkey for b in c), flusso)

    def test_il_blob_conserva_la_sua_lunghezza(self):
        originale = [p for h, _ in SESSIONE for p in [bytes.fromhex(h)]
                     if p[:2] == b"\x56\x21"]
        riscritti = [p for p, _ in session.costruisci(lighting=LUCE)
                     if p[:2] == b"\x56\x21"]
        self.assertEqual(len(originale), len(riscritti))


class Layout(unittest.TestCase):
    def test_le_tre_numerazioni_tornano(self):
        from layout import (indice_colonne, posizione, tasto,
                            tasto_da_indice_colonne)
        for riga in range(1, 6):
            for colonna in range(1, 6):
                codice = tasto(riga, colonna)
                if codice is None:
                    continue                     # la posizione in piu dello spazio
                self.assertEqual(posizione(codice), (riga, colonna))
                indice = indice_colonne(riga, colonna)
                self.assertEqual(tasto_da_indice_colonne(indice), codice)

    def test_ventiquattro_tasti_su_venticinque_posizioni(self):
        self.assertEqual(len(tutti_i_tasti()), 24)
        self.assertEqual(sum(1 for r in GRIGLIA for k in r if k is None), 1)

    def test_la_posizione_senza_tasto_e_un_errore_esplicito(self):
        from layout import tasto_da_indice_colonne
        with self.assertRaises(KeyError):
            tasto_da_indice_colonne(24)      # la seconda meta dello spazio
        with self.assertRaises(KeyError):
            tasto_da_indice_colonne(25)

    def test_ogni_altro_indice_ha_il_suo_tasto(self):
        from layout import tasto_da_indice_colonne
        codici = [tasto_da_indice_colonne(i) for i in range(24)]
        self.assertEqual(sorted(codici), sorted(tutti_i_tasti()))


if __name__ == "__main__":
    unittest.main()
