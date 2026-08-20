---
title: The pad accepts one HID handle at a time, and sends no unsolicited reports on macOS
verified: 2026-08-20
applies-to: ControlPadEngine/bridge.py, session.py, indicatori.py, any device probe
---

## What is true

On macOS the ControlPad accepts **one handle only**. While `ControlPad.app` is
open, every diagnostic script fails with `open failed`, and vice versa.

Three consequences, all measured on 2026-08-20:

- The rule applies **inside** the engine too. While the indicator-animation thread
  holds the device, the listening thread cannot open it. That is why state is
  queried over the animation's own handle
  (`indicatori.riproduci_finche(fra_i_fotogrammi=...)`) instead of opening a
  second one.
- The pad's **unsolicited reports** (`52 00`, `52 28`, `43 01`) do **not** reach
  the handle on macOS: thirty seconds of continuous reading yielded zero packets.
  They do arrive on Windows, which is why the captures contain them. State must
  therefore be **asked for** (`52 00 00 00`, `52 28 00 00`), never waited for.
- Opening and closing the device in rapid succession knocks it off the bus. During
  testing it disappeared from USB entirely and needed the cable unplugged. Prefer
  one handle held open for the whole test.

## Why it bites

A probe reports "zero key presses" while keys are actually being pressed, and the
natural conclusion — that the protocol decoding is wrong — is false. Two probes
were written on that mistaken basis.

## What to do

Quit the app before any test on the pad:

```bash
pkill -f 'ControlPad.app' ; pgrep -fl ControlPad   # expect no output
```

Ask for state explicitly rather than waiting for a report. Hold a single handle
open for the duration of a test instead of reopening per command.

## What does not prove anything

The absence of incoming reports. On macOS that is the expected behaviour, not
evidence about the protocol or about whether the device registered anything.
