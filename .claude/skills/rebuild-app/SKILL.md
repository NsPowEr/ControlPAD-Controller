---
name: rebuild-app
description: Rebuild ControlPad.app from source and relaunch it. Use whenever a change to the Python engine or the SwiftUI code needs to be seen in the real app, because the running app executes the engine copy inside the bundle, not the repository sources.
disable-model-invocation: true
---

# Rebuilding and relaunching ControlPad.app

The app runs the copy of `ControlPadEngine/` that lives **inside the bundle**, not
the sources in the repository. Until the bundle is rebuilt, edits to the Python
engine have no effect on what is on screen. This is the single most common cause
of "I fixed it but nothing changed".

The pad accepts **one handle at a time**: if the old instance is still running,
the new one cannot open the device, and command-line probes lie in both
directions. Always quit before relaunching. See
[one-hid-handle](../../procedures/one-hid-handle.md).

## Procedure

1. Quit the running instance and confirm it is really gone:

   ```bash
   osascript -e 'quit app "ControlPad"' 2>/dev/null || true
   pkill -f 'ControlPad.app/Contents/MacOS/ControlPad' 2>/dev/null || true
   pgrep -fl ControlPad   # expect no output
   ```

2. Rebuild the bundle — this compiles in release, copies the Python engine, signs
   the app and installs it outside iCloud:

   ```bash
   ./ControlPadGUI/scripts/make_app_bundle.sh
   ```

   `swift build` alone is **not** enough: it never refreshes the engine copy.

3. If step 2 fails to compile, report the error verbatim and stop. Do not relaunch
   the old build and present it as the new one.

4. Relaunch the installed copy:

   ```bash
   open ~/Applications/ControlPad.app
   ```

   The project lives on the Desktop, which is synced with iCloud on this machine;
   reading resources from there can stall inside `open()`. The script installs to
   `~/Applications` for that reason, so prefer that copy over
   `ControlPadGUI/dist/ControlPad.app`.

## Confirm the bundle is actually fresh

A stale bundle announces itself in no way at all. Compare timestamps before
claiming a change is live:

```bash
ls -lT ~/Applications/ControlPad.app/Contents/Resources/ControlPadEngine/bridge.py
ls -lT ControlPadEngine/bridge.py
```

The bundled copy must be at least as recent as the source. A sharper check is to
grep the bundled engine for a symbol that only exists in the new code:

```bash
grep -c '<new_function_name>' ~/Applications/ControlPad.app/Contents/Resources/ControlPadEngine/bridge.py
```

## When something still does not respond

The engine journal is at `~/Library/Logs/ControlPad-engine.log`. Read it before
looking anywhere else — errors already fixed in the sources still showing up
there mean the bundle is stale, not that the fix is wrong.

## What proves nothing

Running an engine script by hand while the app is open. The device is already
taken, reports do not arrive, and the result misleads in both directions. Quit
the app first, then probe.
