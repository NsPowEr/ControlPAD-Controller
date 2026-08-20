---
title: Profile +/- is emulated by the app, not reproducible over the firmware protocol
verified: 2026-08-20
applies-to: ControlPadEngine/session.py, ControlPadGUI/Sources/ControlPadGUI/Models/ProfileStepTap.swift
---

## What is true

**`51 94` has nothing to do with the profile step.** Measured on the pad on
2026-08-20: with the table intact, the keys already assigned by MasterPlus
(`a` forward, `d` back) still step; removing the slot from arbitrary keys
(`q`, `w`, `s`, `e`, Space, `4`) changes nothing — they type their own letter.
`51 90` does not select the direction either: it was identity at every index
while `a` and `d` stepped in opposite directions.

What arms a key is a **global, sticky** assignment that only the official
software writes. It survives a factory session and all of ours, and appears in
none of the 24 captures, in no table (`52 00`–`52 ff` at every index), and
nowhere in memory (`0x0000`–`0x0c00`).

## Why it bites

Every attempt to reproduce the step through the firmware protocol looks like it
is one experiment away from working, and is not. Because the assignment is
global, a test can also measure the assignment left behind by an earlier run.

## What to do

The app emulates it. `session.PASSO_HID` assigns F13 (`0x68`) for forward or
F14 (`0x69`) for back to the key, and `ProfileStepTap` (a `CGEventTap` in
`ControlPadGUI/Sources/ControlPadGUI/Models/ProfileStepTap.swift`) intercepts the
event, swallows it, and calls `AppModel.stepHardwareBank`. This works on any key
and on the wheels. It requires the app to be running and the Accessibility
permission to be granted.

Since the bundle is signed with a stable identity, that permission survives
rebuilds; with an ad-hoc signature it has to be granted again after every build.

## What does not prove anything

Any test run without first clearing the existing assignment. To reopen the
firmware route, a Windows capture starting from a clean state is needed: first
**remove** Profile +/- from the keys that have it and save, then assign it
elsewhere. The existing captures only show the assignment already in place.
