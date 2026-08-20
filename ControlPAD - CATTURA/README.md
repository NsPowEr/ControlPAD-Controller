# ControlPad — Reverse Engineering & Protocol Guide

Complete control of the **Cooler Master ControlPad** (`VID 0x2516` / `PID 0x007B`, Cherry MX variant) without the official software, which is Windows-only.

Everything documented here was **reverse-engineered from raw USB packet captures** in `captures/` and **verified on physical hardware**. Where a behavior is inferred rather than tested, it is explicitly noted.

> **Code Location.** The core communication library resides in **`../ControlPadEngine/`**, which is embedded inside the standalone macOS application bundle. This folder houses raw captures, protocol documentation, and diagnostic tools.

---

## 1. Environment Setup

Requires Python 3 and a single USB HID library.

```bash
# Verify Python 3
python3 --version

# Install HIDAPI interface
pip3 install hidapi
```

If `pip3 install hidapi` fails due to missing system headers on macOS:
```bash
brew install hidapi
pip3 install hidapi
```

Then plug in the ControlPad.

---

## 2. Hardware Verification

Run these verification commands in order from `../ControlPadEngine/`:

```bash
cd ../ControlPadEngine

# 1. Does macOS recognize the device?
python3 -c "import hid; print([d['path'] for d in hid.enumerate(0x2516, 0x007B)])"

# 2. Illuminate the entire pad in red
python3 -c "from controlpad import ControlPad; pad = ControlPad(); pad.set_static(255, 0, 0); pad.close()"

# 3. Animate the top 4 indicator LEDs
python3 ../Come_usare_manipolare_i_4_led/anim.py

# 4. Run the offline test suite (no hardware required)
python3 -m unittest discover -s tests
```

---

## 3. Physical Layout & Key Identification

24 mechanical keys arranged on a 5×5 matrix (the bottom row has 4 keys as the Spacebar occupies two grid positions), plus two rotary dials and four top indicator LEDs.

```
   LEFT DIAL                               RIGHT DIAL
                         ●  ●  ●  ●        ← 4 Indicator LEDs

   `     1     2     3     4
   Tab   q     w     e     r
   Caps  a     s     d     f
   Shift z     x     c     v
   Ctrl  ·     Alt   [   Space   ]
```

The keys match the left portion of a standard QWERTY keyboard layout by default. The key at grid coordinate (3, 3) corresponds to `s` (`0x16`).

### The Three Numbering Schemes — The Core Pitfall

The firmware references the 24 physical keys using **three distinct numbering systems**:

| Numbering | Usage Scope |
|---|---|
| **Default HID Keycode** | Key remapping commands, macro slot assignments |
| **Column-Major Index** | Per-key LED color table, profile selector table |
| **Row-Major Index** | Keymap upload sequence order (`51 20` / `51 80`) |

`layout.py` automatically converts between all three systems:

```python
from layout import tasto, indice_led, posizione

tasto(3, 3)        # 0x16  — Default HID code for row 3, column 3
indice_led(3, 3)   # 16    — LED offset in color table
posizione(0x16)    # (3, 3)
```

---

## 4. Hardware Persistence vs. Live State

- **Stored permanently in firmware flash**: Macros, key remappings, special functions, profile assignments. Written once, they persist across power cycles and function on any OS without software running.
- **Applied dynamically**: Backlighting colors and active lighting effect modes. The official Windows utility also uses a resident background service to re-apply lighting when the device connects.
- **Exception**: The 4 top indicator LEDs maintain the last written RGB state even across complete USB power disconnection.

---

## 5. Driver API Examples

### Live Key Backlighting

```python
from controlpad import ControlPad, led_index

with ControlPad() as pad:
    pad.set_static(255, 0, 0)                  # All keys static red
    pad.set_effect(0x31, 0, 0, 255, speed=8)   # Color cycle animation
    pad.set_grid({(0, 0): (255, 0, 0),         # Specific keys
                  (2, 2): (0, 255, 0)})
```

### Top 4 Indicator LEDs

```python
with ControlPad() as pad:
    pad.set_indicators([(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255)])
```

The indicator LEDs support up to **250 updates per second** without transaction commits and **167 fps** with commits, enabling smooth live frame animations.

### Permanent Configuration Writing

```python
from session import scrivi, FUNZIONI
from macro import events_for, events_for_combo, LCTRL, LALT, DEL
from layout import tasto, indice_colonne

scrivi(
    macros=[
        (8, tasto(1, 1), events_for("Hello World"), "greeting"),
        (9, tasto(1, 2), events_for_combo([LCTRL, LALT, DEL]), "taskmgr"),
    ],
    remaps={
        tasto(2, 1): 0x3E,                      # Remap to F5
        tasto(2, 2): FUNZIONI["volume_su"],     # Remap to Volume Up
    },
    profile_keys={
        indice_colonne(4, 1): 0,                # Switches directly to Profile 1
    },
)
```

---

## 6. Critical Implementation Details

- **Write applies to the active profile**: The device maintains independent keymaps per profile bank. Always ensure the intended profile bank is active when writing.
- **ACK queue draining**: The hardware emits unsolicited `ff aa` reports. Drivers must drain the IN queue until the matching opcode ACK is received.
- **Flash delay**: Each macro write requires a ~72 ms settlement delay before the next command.
- **14 lighting slots**: The firmware defines 14 distinct lighting slots (`56 15`), each holding independent parameters and reactive colors.
