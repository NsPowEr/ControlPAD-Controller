# Cooler Master ControlPad — USB Protocol Specification

Reverse-engineered from raw USB packet captures in `captures/` and verified by transmitting commands to physical hardware and observing physical responses.

Target Hardware Model: **ControlPad (Cherry MX Switches)**, `VID 0x2516` / `PID 0x007B`.  
*Note: OpenRGB issue #2448 pertains to PID `0x012D` (Gateron variant) and remains unimplemented; this work was conducted independently.*

---

## 1. Communication Channel

| Property | Value |
|---|---|
| Interface | `MI_01` — Usage Page `0xFF00` (Vendor-Defined) |
| Endpoints | `0x04` OUT, `0x83` IN (Interrupt transfers) |
| Report Size | 64 bytes |
| Report ID | None (unnumbered) |

*Using `hidapi`, a `0x00` Report ID prefix byte must be prepended, sending 65 bytes per `write()` call. Other interfaces (`MI_00`, `MI_02`) represent standard keyboard and multimedia controls and will reject vendor configuration commands.*

Every OUT report receives an acknowledgment (ACK) on the IN endpoint echoing the header with remaining bytes zeroed (`56 83 ...` → `56 83 00 00 ...`). The device also emits unsolicited reports starting with `ff aa` (key and rotary dial state updates); these must be drained and ignored rather than treated as errors.

---

## 2. Core Command Set

| Opcode | Function |
|---|---|
| `56 81` | Handshake / Session initialization |
| `56 83` | Lighting / Color write |
| `41 80` | Transaction commit |
| `51 28 00 00 ff` | Apply configuration (`ff` apply, `00` release) |
| `56 15`, `56 21` | Profile / Keymap payload framing |

The handshake selects the operational mode:

```
56 81 00 00 01 00 00 00 01 00 00 00 55 55 55 55   Static color mode
56 81 00 00 01 00 00 00 02 00 00 00 bb bb bb bb   Custom per-key color table
```

*Note: Attempting to write a per-key table with a static handshake does not return an explicit error; only keys in chunk 0 light up.*

### Static Backlighting

A single 64-byte report with RGBA at offset 16 (the 4th byte is brightness; 0 turns the LEDs off regardless of RGB):

```
56 83 00 00 01 00 00 00 00 01 00 c1 00 00 00 00 | RR GG BB AA
```

### Per-Key Color Table

Distinguished from static by byte 8 (`0x80` instead of `0x00`) and byte 11 (`0x00` instead of `0xc1`). The 112-byte payload buffer is split across two reports:

```
chunk 0:  56 83 00 00 01 00 00 00 80 01 00 00 | data[0:52]
chunk 1:  56 83 01 00                         | data[52:112]
```

Inside the buffer, colors are **3-byte RGB triplets** without an alpha byte. The first 12 bytes are a fixed header (`ff 00 00 00 00 00 ff ff 00 00 00 00`). Grid keys begin at triplet 4 and proceed **column-by-column**, top-to-bottom, left-to-right:

```
index = 4 + column * 5 + row        (0-based, origin at top-left)
offset = index * 3
```

*The top 4 indicator LEDs are not part of this table; they have independent addressing (`0x00f0`+).*

---

## 3. Full Transmission Sequence

```
Handshake (56 81) → Chunk 0 (56 83) → Chunk 1 (56 83) → Commit (41 80) → Apply (51 28 ... ff)
```

---

## 4. Macros & Key Remapping

Macros do not pass through the profile blob `56 21`; they use dedicated commands. They are saved in **on-board flash memory**: when a key is pressed, the hardware microcontroller directly emits HID codes over keyboard endpoint `0x81` without requiring host software.

### Default HID Key Identification

Every physical key is identified by its default factory HID code, organized like the left side of a standard QWERTY keyboard. Upload order (`51 20` / `51 80`) by row (indices 0–23):

| Row | Default HID Codes |
|---|---|
| 1 | `35` \` · `1e` 1 · `1f` 2 · `20` 3 · `21` 4 |
| 2 | `2b` Tab · `14` q · `1a` w · `08` e · `15` r |
| 3 | `39` Caps · `04` a · `16` s · `07` d · `09` f |
| 4 | `e1` LShift · `1d` z · `1b` x · `06` c · `19` v |
| 5 | `e0` LCtrl · `c0` Function · `e2` LAlt · `2c` Space (double width) |

### Macro Packet Encoding

```
53 00 <num_events> 00 | events × n
```

Each micro-event is 4 bytes: `[HID_code, type, delay_lo, delay_hi]`, with millisecond delay in 16-bit little-endian and type `3c` = keydown, `5c` = keyup. Terminator event: `00 fc fe ff`.

Example: typing uppercase `A`:
```
e1 3c 96 04    LeftShift  keydown    delay 1174 ms
04 3c 08 01    'a'        keydown    delay  264 ms
04 5c 28 00    'a'        keyup      delay   40 ms
e1 5c 00 00    LeftShift  keyup      delay    0 ms
00 fc fe ff    terminator
```

### Key Assignment

```
51 18 <slot> 00 <key_default_HID> 3c     Binds slot to physical key
51 19 <slot> 00 41 00                    Macro properties / name label
53 00 <n> 00 <events>                    Macro body
```

Slots are allocated sequentially (0 to 23). The app clears all 24 slots with `51 18 <i> 00 ff 3f` before uploading.

### Simple Key Remapping

Uses the keymap table:
```
51 20 <default_code> 00 <target_code> 00
51 80 <row_index> 00
```
Setting target code to `ff` maintains default behavior. Remapping top-left key to F5 (`0x3e`):
```
51 20 35 00 ff 00   →   51 20 35 00 3e 00
```

---

## 5. The 14 Lighting Effect Slots

The hardware maintains 14 distinct lighting slots via the `56 15` table:

| Slot | Official Name | Type | Offset | Size | Marker |
|---|---|---|---|---|---|
| `00` | Static | 1 | 4 | 6 | `55555555` |
| `01` | Rainbow Wave | 1 | 10 | 12 | `55555555` |
| `02` | Crosshair | 2 | 22 | 12 | `00000000` |
| `03` | Reactive Fade | 2 | 34 | 29 | `00000000` |
| `04` | Custom | 1 | 63 | 11 | `bbbbbbbb` |
| `05` | Stars | 2 | 74 | 13 | `00000000` |
| `06` | Snow | 2 | 87 | 8 | `00000000` |
| `07` | Color Cycle | 1 | 95 | 6 | `55555555` |
| `08` | Blink | 1 | 101 | 9 | `55555555` |
| `09` | Reactive Punch | 2 | 110 | 9 | `00000000` |
| `0a` | Circular Spectrum | 1 | 119 | 7 | `55555555` |
| `0b` | Reactive Tornado | 1 | 126 | 10 | `55555555` |
| `0c` | Water Ripple | 2 | 136 | 5 | `00000000` |
| `0d` | Off | 1 | 141 | — | `aaaaaaaa` |

- **Type 1 (Single color / Non-reactive)**: Static, Rainbow wave, Blink, Color cycle, Circular spectrum, Reactive tornado, Custom, Off.
- **Type 2 (Dual color / Reactive touch)**: Crosshair, Reactive fade, Stars, Snow, Reactive punch, Water ripple. Supports base background tint + reaction color.

---

## 6. Special Internal Functions & Rotary Dials

Actions `≥ 0x0100` represent internal device functions:

| Code | Function | | Code | Function |
|---|---|---|---|---|
| `00ff` | Factory default (no remap) | | `0181` | Effect cycle forward (+) |
| `00f0` | Play / Pause | | `0182` | Effect cycle backward (−) |
| `00f1` | Stop | | `0190` | Speed down (−) |
| `00f2` | Previous Track | | `0191` | Speed up (+) |
| `00f3` | Next Track | | `0192` | LED brighter (+) |
| `00f4` | Mute | | `0193` | LED darker (−) |
| `00f5` | Volume down (−) | | `0110` | Select Profile |
| `00f6` | Volume up (+) | | | |

Rotary dials are addressed as pseudo-keys: Left Dial CCW/CW = `c6`/`c7`, Right Dial CCW/CW = `f5`/`f6`.

---

## 7. Profile Indicator LEDs

The 4 top indicator LEDs reside at address `0x00f0 + bank * 12`:

```
41 04                                      Open transaction (mandatory)
55 50 <addr_lo> <addr_hi> 0c <R G B> × 4   Write 12 RGB bytes
41 80                                      Commit (optional, omitted for high fps)
```

Each of the 24 profile banks has its own 12-byte slot:
- Bank 0 (Profile 1): `0x00f0`
- Bank 1 (Profile 2): `0x00fc`
- Bank 23 (Profile 24): `0x0204`

---

## 8. Hardware Quirks & Discovery Summary

1. **ACK Queue Draining**: Must read IN endpoint until matching opcode ACK returns.
2. **Flash Delay**: Requires ~72 ms settlement pause after each macro payload write (`53 00`).
3. **Double Commit for Bank Switching**: `51 00 00 00 <bank>` must be enclosed between two `41 80` commits.
4. **Profile Step Keys**: Configured by clearing the key from `51 94` table (`ff ff ff ff`) and setting direction in `51 90` table.
