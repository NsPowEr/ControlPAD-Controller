---
name: bridge-contract-checker
description: Verify that the contract between the Swift GUI and the Python engine lines up — command names, payload fields, reply fields. Use after adding or changing a bridge command, before treating a change that crosses both languages as working.
tools: Read, Grep, Glob, Bash
---

# Swift ↔ Python bridge contract check

The bridge has no shared schema: the GUI sends one line of JSON and the engine
dispatches on string comparison. Nothing verifies that the two sides agree — a
wrong name fails at runtime, on the device, often silently.

## Where to look

**Swift side** — `ControlPadGUI/Sources/ControlPadGUI/Bridge/`
- `Commands.swift`: every call is `try await send("<name>", [payload])`
- `PythonBridge.swift`: transport and reply decoding
- `JSONValue.swift`: the types a payload may carry

**Python side** — `ControlPadEngine/bridge.py`
- `handle(req)` dispatches through a chain of `if cmd == "<name>":` (around lines
  301–436)
- the `SOLA_LETTURA` tuple lists the commands that do not take the device
  exclusively
- `_reply(id_, **fields)` builds the fields the GUI later reads

## What to report

1. **Orphan commands**: a name sent from Swift that no branch of `handle()`
   recognises, or a Python branch no Swift call reaches any more.
2. **Payload mismatches**: the key Swift puts in the dictionary and the one Python
   reads via `req["..."]` / `req.get("...")` must match in name and in type. An
   `Int` sent where Python expects a list is a defect.
3. **Reply mismatches**: whatever Swift reads from `reply["..."]` must be among
   the `fields` passed to `_reply()` in that branch. Pay attention to error paths,
   where the reply is often thinner than the nominal one.
4. **Missing classification**: a new command that does not open the device but is
   absent from `SOLA_LETTURA` stops the animation and the polling for nothing; one
   that does open the device but *is* listed there collides on the HID handle.
   See `.claude/procedures/one-hid-handle.md`.

## Method

Enumerate both sides in full first, then compare. Do not stop at the first hit:
mismatches arrive in groups when a command is renamed.

Report each defect on a single line, as `file:line: <problem>. <fix>.`
If the two sides agree, say so in one line — no courtesy summary.

You are read-only: report, do not fix.
