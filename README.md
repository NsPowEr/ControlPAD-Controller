# ControlPAD Controller for macOS

[![CI](https://github.com/NsPowEr/ControlPAD-Controller/actions/workflows/ci.yml/badge.svg)](https://github.com/NsPowEr/ControlPAD-Controller/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/NsPowEr/ControlPAD-Controller)](https://github.com/NsPowEr/ControlPAD-Controller/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform: macOS](https://img.shields.io/badge/Platform-macOS-black?logo=apple)](https://apple.com)
[![Swift 6.2](https://img.shields.io/badge/Swift-6.2-orange.svg?logo=swift)](https://swift.org)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg?logo=python)](https://python.org)

Complete, native control software for the **Cooler Master ControlPad** (`VID 0x2516` / `PID 0x007B`, Cherry MX switch variant) on **macOS**.

The official Cooler Master software (*MasterPlus+*) is strictly Windows-only, resource-intensive, and prone to crashes. This project liberates the hardware on Mac, providing an ultra-responsive native **SwiftUI (Liquid Glass)** user interface backed by a reverse-engineered low-level USB HID communication engine.

---

## 🌟 Key Features

- **⚡ Native & Fluid macOS Experience**: Built with modern SwiftUI and Apple's *Liquid Glass* design system, full dark/light mode support, runtime multi-language switching (English & Italian), and zero heavy runtime dependencies.
- **🎯 Multi-Disciplinary Professional Versatility**:
  - **Video & Audio Post-Production**: Precise frame-by-frame scrubbing and timeline navigation using the dual precision dials for DaVinci Resolve, Final Cut Pro, Logic Pro, and Premiere.
  - **3D Modeling & Graphic Design**: Rapid shortcut triggering and custom macros for Blender, Photoshop, Illustrator, and CAD.
  - **Software Engineering & Terminal Power Users**: One-touch Git commands, terminal navigation, snippet insertion, and window tiling shortcuts.
  - **macOS Gaming**: Custom input mapping with ultra-low latency response.
- **💾 Firmware Flash Persistence (On-Board Memory)**:
  - **Macros, 24-key remappings, special functions, and profile selections** are written directly to the device's hardware flash memory. Once configured, they work autonomously on any computer without background software.
- **🌈 Complete RGB Lighting Control**:
  - 14 lighting effect modes (Static, Rainbow Wave, Crosshair, Reactive Fade, Custom Per-Key, Stars, Snow, Color Cycle, Blink, Reactive Punch, Circular Spectrum, Reactive Tornado, Water Ripple, Off).
  - Custom per-key RGB coloring and reaction tint customization.
- **💡 4 Profile Indicator LEDs Animation Engine**:
  - Full addressability and frame-by-frame live animation engine for the top 4 status LEDs (the last written state persists even across USB disconnects).
- **🛡️ Robust & Resilient Architecture**:
  - Over 130 automated unit tests across the Python engine and Swift GUI.
  - Automatic draft state preservation (`draft.json`) with `.bak` safety fallbacks to prevent configuration loss.

---

## 📂 Project Architecture

| Directory | Description |
|---|---|
| [`ControlPadEngine/`](ControlPadEngine/) | **The Engine**: Low-level USB HID driver, hardware session manager, macro and lighting effect encoders, JSON IPC bridge subprocess. |
| [`ControlPadGUI/`](ControlPadGUI/) | **macOS App**: Native SwiftUI interface (Liquid Glass) with Lighting, Key Mapping, Macros, Profiles, and Settings tabs. |
| [`ControlPAD - CATTURA/`](ControlPAD%20-%20CATTURA/) | **Reverse Engineering**: Raw Wireshark `.pcapng` USB packet captures and comprehensive protocol specifications in [`PROTOCOL.md`](ControlPAD%20-%20CATTURA/PROTOCOL.md). |
| [`Come_usare_manipolare_i_4_led/`](Come_usare_manipolare_i_4_led/) | **LED Manipulation**: Primitive animation algorithms, time/space transforms, and persistence tests for the 4 top LEDs. |

---

## 🚀 Quick Start

### Prerequisites
- **macOS 14+** (with optimal support for macOS 26 Liquid Glass SDK).
- **Python 3.11+** with the `hidapi` package.

### Installation & Launch

```bash
# 1. Clone the repository
git clone https://github.com/NsPowEr/ControlPAD-Controller.git
cd ControlPAD-Controller

# 2. Install the single Python dependency
pip3 install hidapi

# 3. Verify engine tests (runs offline without hardware connected)
python3 -m unittest discover ControlPadEngine/tests

# 4. Launch the SwiftUI application in development mode
cd ControlPadGUI
swift run
```

To build and package a standalone macOS `.app` bundle into `~/Applications`:
```bash
cd ControlPadGUI
./scripts/make_app_bundle.sh
```

---

## 🔬 Hardware Protocol Insights

Before extending communication logic, review the reverse engineering specifications:
- 📖 [**`ControlPAD - CATTURA/PROTOCOL.md`**](ControlPAD%20-%20CATTURA/PROTOCOL.md) — Byte-by-byte breakdown of USB HID packets (`0x04` OUT / `0x83` IN endpoints, `56 83` color headers, column-major matrix indexing, macro micro-event structure).
- ⚠️ [**`ControlPAD - CATTURA/README.md`**](ControlPAD%20-%20CATTURA/README.md) — Hardware quirks uncovered during capture analysis (the 3 distinct numbering schemes for the 24 keys, flash write delays, ACK queue draining rules).

---

## 🤝 Contributing

Contributions from the community are warmly welcomed! Please check [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines and [CHANGES.md](CHANGES.md) for version history.

---

## 📜 License

This project is licensed under the [MIT License](LICENSE).  
All product and brand names (*Cooler Master*, *ControlPad*, *MasterPlus+*, *Aimpad*, *Cherry MX*) are trademarks of their respective owners.
