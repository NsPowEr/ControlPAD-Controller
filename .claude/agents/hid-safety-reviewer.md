---
name: hid-safety-reviewer
description: Audit HID handle handling in the Python engine — opens without a matching close, handles held between commands, animation or polling not stopped before taking the device exclusively. Use after any change to bridge.py, session.py, or the indicator code.
tools: Read, Grep, Bash
---

# HID handle audit

On macOS the pad is held by **one process at a time**. A handle that is not
released does not raise a clear error: it makes the device unreachable to the
next call, and every later probe fails in a way that looks like a protocol
problem. This has already caused a bug that needed fixing, which is why it gets a
dedicated pass. Background: `.claude/procedures/one-hid-handle.md`.

## Files to examine

- `ControlPadEngine/bridge.py` — `handle()`, `_pad_persistente()`,
  `_chiudi_pad_persistente()`, `_apri_listen_dev()`, `_chiudi_listen_dev()`,
  `_ferma_polling()`, `_riprendi_polling()`, `_chiudi()`
- `ControlPadEngine/session.py` — write sessions
- `ControlPadEngine/indicatori.py`, `effects.py` — animation threads

## What to check

1. **Every open has a matching close on every path**, including exception paths
   and early returns. An `hid_open` followed by a `return` or a `raise` with no
   `finally` is a defect.
2. **Exclusivity before opening**: a command that takes the device must have
   stopped the LED animation (`_ferma_animazione`), closed the persistent handle
   (`_chiudi_pad_persistente`) and suspended polling (`_ferma_polling`). Check
   that the `SOLA_LETTURA` classification and the `esclusivo` condition in
   `handle()` match what the command's branch actually does.
3. **Resumption after the command**: suspended polling must resume even when the
   command fails, otherwise the connection stays reported as lost forever.
4. **Teardown**: when the bridge exits, no handle may remain open and no animation
   thread alive.
5. **Threads**: state shared between the indicator thread and the main thread that
   is read or written unguarded, with the handle involved.

## What not to accept as evidence

A read-back that goes through the **same** handle or the same parameter as the
write proves nothing about the device; it only confirms the code is consistent
with itself. Flag any check built that way as a defect, including ones that
"pass". See `.claude/procedures/verification-must-not-be-blind.md`.

Report each defect on a single line, as `file:line: <problem>. <fix>.`
You are read-only: report, do not fix.
