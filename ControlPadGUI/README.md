# ControlPad — macOS App

Native SwiftUI application (Liquid Glass, macOS 26+) for the Cooler Master ControlPad, featuring the same four core tabs as the official Windows software: Lighting, Key Mapping, Macros, Profiles — plus a Settings panel with runtime language selection and diagnostics.

The USB protocol is decoupled from the UI: this app drives the device by spawning `../ControlPadEngine/bridge.py` as a child subprocess and communicating via JSON over stdin/stdout. The core hardware communication logic (handshake, timings, macro encoding, ACK queue draining) lives cleanly in `ControlPadEngine/`, verified on physical hardware — see `../ControlPAD - CATTURA/PROTOCOL.md` for byte-level specifications.

---

## Running in Development

```bash
cd ControlPadGUI
swift run
```

Requires `ControlPadEngine/` alongside this directory (as organized in the repository) and Python 3 with `hidapi` installed — see `../ControlPadEngine/requirements.txt`:

```bash
pip3 install hidapi
```

---

## Packaging as an Application Bundle

```bash
./scripts/make_app_bundle.sh
open dist/ControlPad.app
```

The script compiles the package in release configuration and creates `dist/ControlPad.app` with the executable, bundled localized resources, and an embedded copy of `ControlPadEngine/` inside `Contents/Resources/`, enabling standalone execution. Ad-hoc code signing is included for local use.

**PATH Handling Note**: An application launched via Finder inherits launchd's minimal PATH rather than interactive shell environment variables. `PythonBridge` resolves the correct `python3` binary from the user's login shell (where `pip3 install hidapi` was executed) rather than relying on `/usr/bin/env python3`.

---

## Architecture & Layout

See `Sources/ControlPadGUI/`:
- `Bridge/`: JSON IPC communication with the Python engine.
- `Models/`: Key layout models, lighting effect definitions, special functions, preset store.
- `Views/`: The 4 main feature tabs, Settings view, and shared components (Liquid Glass tab bar, key grids, bank selectors).
- `Localization.swift`: Dynamic runtime locale switcher supporting English (`en`) and Italian (`it`).

---

## Feature Overview

- **Lighting**: All 14 lighting modes unlocked. The 6 reactive modes support dual color selectors (base tint and reactive pulse). Custom mode allows visual per-key RGB coloring.
- **Key Mapping**: Visual 5x5 pad layout mirroring hardware keys **1–24**, accompanied by a full keyboard picker and dedicated media/lighting/profile function selectors.
- **Macros**: Interactive live recording capturing real keydown/keyup events and precise millisecond intervals, with manual timing adjustments.
- **Profiles**: Host-side presets saved in `~/Library/Application Support/ControlPad/presets.json` alongside hardware bank selectors for the device's 24 internal on-board memory banks.

---

## Testing

Engine tests (runs offline without device):
```bash
cd ../ControlPadEngine && python3 -m unittest discover -s tests
```

Swift UI and model tests:
```bash
cd ControlPadGUI && swift test
```
