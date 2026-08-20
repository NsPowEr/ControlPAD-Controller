---
title: The app runs the engine copy inside the bundle, not the repository sources
verified: 2026-08-20
applies-to: ControlPadEngine/**, ControlPadGUI/scripts/make_app_bundle.sh
---

## What is true

`ControlPad.app` executes the copy of `ControlPadEngine/` stored in
`Contents/Resources/`, not the sources in the repository. Editing Python without
rebuilding the bundle changes nothing in what the user actually tries.

`swift build` does not refresh that copy. Only
`ControlPadGUI/scripts/make_app_bundle.sh` does: it compiles in release, copies
the engine, signs the app, and installs it to `~/Applications/ControlPad.app`
(the project lives on an iCloud-synced Desktop, and reading resources from there
can stall inside `open()`).

## Why it bites

Fixes appear to have no effect. On 2026-08-20 several correct fixes looked broken
for about an hour: the engine log kept showing errors that had already been
fixed in the sources, because the bundle was still a previous build.

## What to do

After any change to the engine, rebuild the bundle **before** asking anyone to
try it, and have them reopen the app. When a symptom does not change after a
fix, check the bundle before looking anywhere else:

```bash
grep -c '<new_function_name>' ~/Applications/ControlPad.app/Contents/Resources/ControlPadEngine/bridge.py
```

The engine journal is at `~/Library/Logs/ControlPad-engine.log`. It is the first
thing to read when something stops responding.

## What does not prove anything

Reading the repository sources to confirm a fix is present. They are not what is
running. Confirmation has to come from the bundled copy or from the engine log.
