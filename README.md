# ControlPAD Controller for macOS

[![CI](https://github.com/NsPowEr/ControlPAD-Controller/actions/workflows/ci.yml/badge.svg)](https://github.com/NsPowEr/ControlPAD-Controller/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform: macOS](https://img.shields.io/badge/Platform-macOS-black?logo=apple)](https://apple.com)
[![Swift 6.2](https://img.shields.io/badge/Swift-6.2-orange.svg?logo=swift)](https://swift.org)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg?logo=python)](https://python.org)

Controllo nativo completo per il tastierino meccanico/analogico **Cooler Master ControlPad** (`VID 0x2516` / `PID 0x007B`, variante Cherry MX) su **macOS**.

Il software ufficiale Cooler Master (*MasterPlus+*) è disponibile unicamente per Windows ed è spesso soggetto a crash, pesantezza e tempi di configurazione lenti. Questo progetto nasce per colmare questa mancanza: libera il potenziale dell'hardware su Mac offrendo un'interfaccia nativa **SwiftUI (Liquid Glass)** reattiva e veloce, supportata da un motore di comunicazione USB HID a basso livello sviluppato interamente tramite **reverse engineering** del protocollo.

---

## 🌟 Caratteristiche Principali

- **⚡ Un'esperienza nativa e istantanea per macOS**: Interfaccia moderna con estetica *Liquid Glass*, supporto dark/light, localizzazione completa (Italiano & Inglese) e zero dipendenze pesanti.
- **🎯 Versatilità Professionale Multiruolo**:
  - **Video & Audio Editing**: Scrubbing e controlli di precisione con le due rotelle per DaVinci Resolve, Final Cut Pro, Logic Pro, Premiere.
  - **Modellazione 3D & Design**: Scorciatoie rapide e macro per Blender, Photoshop, CAD.
  - **Sviluppo & Produttività**: Snippet, navigazione nel terminale, gestione finestre, comandi Git a portata di un solo tasto.
  - **Gaming su Mac**: Mappature personalizzate e layout dedicati.
- **💾 Persistenza nel Firmware Hardware (On-Board Flash)**:
  - **Macro, rimappature dei 24 tasti, tasti funzione e selettori di profilo** vengono scritti direttamente nella memoria flash del pad. Una volta configurati, funzionano su qualsiasi computer senza bisogno di software attivo in background.
- **🌈 Gestione Completa dell'Illuminazione RGB**:
  - 14 modalità di effetto (statico, onda arcobaleno, reattivi al tocco a 2 colori come mirino, dissolvenza, neve, stelle, ciclo colore, ecc.).
  - Mappatura cromatica per-tasto personalizzata.
- **💡 Controllo dei 4 LED Indicatori**:
  - Indirizzamento e animazioni frame-by-frame per i 4 LED superiori (lo stato sopravvive anche allo scollegamento del cavo USB).
- **🛡️ Architettura Resiliente & Testata**:
  - Oltre 130 test unitari automatizzati tra motore Python e interfaccia Swift.
  - Salvataggio automatico del profilo bozza (`draft.json`) con backup resiliente per evitare perdite di dati.

---

## 📂 Struttura del Progetto

| Cartella | Descrizione |
|---|---|
| [`ControlPadEngine/`](ControlPadEngine/) | **Il motore**: Driver USB HID, gestione sessione hardware, codificatori di macro ed effetti, bridge JSON IPC subprocess. |
| [`ControlPadGUI/`](ControlPadGUI/) | **L'app macOS**: Interfaccia SwiftUI nativa (Liquid Glass) con schede Illuminazione, Mappatura Tasti, Macro, Profili e Impostazioni. |
| [`ControlPAD - CATTURA/`](ControlPAD%20-%20CATTURA/) | **Reverse Engineering**: Catture pacchetti Wireshark `.pcapng`, specifiche dettagliate del protocollo byte per byte in [`PROTOCOL.md`](ControlPAD%20-%20CATTURA/PROTOCOL.md). |
| [`Come_usare_manipolare_i_4_led/`](Come_usare_manipolare_i_4_led/) | **LED Indicatori**: Primitive di controllo, sequenze di animazione ed esperimenti di persistenza. |

---

## 🚀 Primi Passi

### Requisiti
- **macOS 14+** (con supporto ottimale per macOS 26 Liquid Glass SDK).
- **Python 3.11+** con libreria `hidapi`.

### Installazione e Avvio Rapido

```bash
# 1. Clona il repository
git clone https://github.com/NsPowEr/ControlPAD-Controller.git
cd ControlPAD-Controller

# 2. Installa l'unica dipendenza Python
pip3 install hidapi

# 3. Verifica i test del motore (anche senza pad collegato)
python3 -m unittest discover ControlPadEngine/tests

# 4. Avvia l'interfaccia grafica SwiftUI
cd ControlPadGUI
swift run
```

Per generare l'applicazione autonoma impacchettata in `~/Applications`:
```bash
cd ControlPadGUI
./scripts/make_app_bundle.sh
```

---

## 🔬 Note sul Protocollo Hardware

Prima di modificare o estendere la logica di comunicazione, consulta la documentazione tecnica:
- 📖 [**`ControlPAD - CATTURA/PROTOCOL.md`**](ControlPAD%20-%20CATTURA/PROTOCOL.md) — La specifica completa del protocollo USB (endpoint `0x04`/`0x83`, header `56 83`, tabella per-tasto per colonne, encoding delle macro in micro-eventi).
- ⚠️ [**`ControlPAD - CATTURA/README.md`**](ControlPAD%20-%20CATTURA/README.md) — Le peculiarità dell'hardware scoperte durante l'analisi (le 3 diverse numerazioni dei 24 tasti, la pausa di scrittura flash, il drenaggio della coda ACK).

---

## 🤝 Contribuire

I contributi della community sono benvenuti! Consulta la [Guida ai Contributi](CONTRIBUTING.md) e il [Changelog](CHANGES.md) per conoscere le linee guida sullo sviluppo e lo storico delle versioni.

---

## 📜 Licenza

Questo progetto è rilasciato sotto licenza [MIT](LICENSE).
Tutti i marchi e i nomi commerciali (*Cooler Master*, *ControlPad*, *MasterPlus+*, *Aimpad*, *Cherry MX*) appartengono ai rispettivi proprietari.
