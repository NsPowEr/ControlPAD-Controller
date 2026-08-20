# Animating ControlPad's 4 Indicator LEDs

Practical guide for writing custom lighting effects and frame animations for the 4 status indicator LEDs located above the key grid on the Cooler Master ControlPad.

---

## 1. Overview & Hardware Architecture

The 4 LEDs above the main key matrix are independently addressed at `0x00f0 + bank * 12` (12 bytes: 4 RGB triplets). Unlike key matrix backlighting, which requires full profile blob framing, these LEDs respond to live vendor commands without flash memory wear:

| Characteristic | Top 4 Indicator LEDs | 5×5 Key Grid |
|---|---|---|
| Command Channel | Live vendor write (`55 50`) | Profile structure upload |
| Reports per Update | 2 (without commit) or 3 | 5 reports |
| Latency / FPS | **4.0 ms (250 FPS)** / **6.0 ms (167 FPS)** | Bulk transaction |
| Flash Wear | None (RAM-based) | High (Flash ROM) |
| Suitability for Animation | **Ideal (up to 250 FPS)** | Static / slow transitions |

---

## 2. Low-Level Protocol

```
41 04                                       Open transaction (mandatory)
55 50 <addr_lo> <addr_hi> 0c  <R G B> × 4   Write 12 RGB bytes
41 80                                       Commit (optional)
```

Omitting `41 80` during live continuous streaming reduces frame latency from 6.0 ms to 4.0 ms, achieving up to 250 fps.

---

## 3. The Animation Model: Time as a Function

All animations in `effetti.py` follow a clean mathematical contract:

```python
def frame(t: float) -> list[tuple[int, int, int]]:
    # t = elapsed seconds since start
    return [c0, c1, c2, c3]  # Four (R, G, B) tuples (0-255)
```

### Key Advantages
- **Frame-Rate Independent**: The same animation runs smoothly at 30, 60, or 120 FPS.
- **Composable & Transformable**: Slow down via `frame(t * 0.5)`, reverse with `frame(-t)`, or layer multiple effects via `fx.strati(background, foreground)`.
- **Testable Offline**: Render frames in unit tests without hardware connected.

---

## 4. Waveforms & Temporal Shaping

All waveform functions accept a normalized phase `0.0..1.0` and return `0.0..1.0`:

| Function | Waveform Profile | Visual Character |
|---|---|---|
| `seno(x)` | Smooth sinusoidal curve | Breathing, organic pulsing |
| `triangolo(x)` | Linear ramp up and down | Constant-velocity pendulum |
| `dente(x)` | Sawtooth ramp | Chasing loops, fill bars |
| `quadra(x, duty)` | Square pulse (on/off) | Alarms, strobe |
| `impulso(x)` | Brief spike | Heartbeat, notification flashes |
| `rumore(x)` | Continuous deterministic noise | Campfire embers, flickering lights |

---

## 5. Spatial Antialiasing (Sub-LED Precision)

With only 4 physical points in a row, integer rounding creates noticeable stepped motion. `fx.punto(pos, color)` implements spatial antialiasing by distributing light across adjacent LEDs using float positions:

```python
fx.punto(1.25, color)  # LED 1 at 75%, LED 2 at 25%
```

This ensures fluid, continuous motion across the 4 LEDs.

---

## 6. Gamma Correction (Perceptual Linearity)

Human vision perceives brightness logarithmically rather than linearly. Raw byte ramps appear to abruptly jump from off to dim. Applying `gamma(color, g=2.2)` restores smooth perceptual fades:

```python
fx.gamma(color, g=2.2)  # Converts 128 to 55 (perceived 50% brightness)
```

---

## 7. Available Stock Effects

The library includes 17 built-in animation presets (`indicatori.py`):
- `cometa` (Comet Chase)
- `pendolo` (Sinusoidal Pendulum)
- `respiro` (Gamma-corrected Breathing)
- `onda` (Color Wave)
- `arcobaleno` (Smooth Rainbow Scroll)
- `brace` (Campfire Embers)
- `polizia` (Strobe Flash)
- `vuMeter` (Continuous Level Meter)
- `notifica` (Multi-stage Notification Alert)
