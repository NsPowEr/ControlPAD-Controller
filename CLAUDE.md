# ControlPAD Controller — working notes for Claude

Native macOS control software for the Cooler Master ControlPad
(`VID 0x2516` / `PID 0x007B`). A SwiftUI app drives a reverse-engineered USB HID
engine written in Python.

Setup, requirements and contribution rules live in `README.md` and
`CONTRIBUTING.md` — they are not repeated here.

## Layout

| Path | What it is |
|---|---|
| `ControlPadGUI/` | SwiftUI app, SPM package, Swift 6.2, macOS 26 |
| `ControlPadGUI/Sources/ControlPadGUI/Bridge/` | JSON-line client that drives the engine |
| `ControlPadEngine/` | Python engine, `hidapi`, one process holding the device |
| `ControlPadEngine/bridge.py` | Command dispatch (`handle()`), the contract with Swift |
| `ControlPAD - CATTURA/` | USB captures — **read-only**, see below |
| `.claude/procedures/` | Facts that cost real effort to establish |

The two sides share no schema: Swift sends `send("name", payload)` and Python
dispatches on `if cmd == "name":`. Nothing checks that they agree — use the
`bridge-contract-checker` agent after touching either side.

## Read this before touching the device

These are measured facts, not conventions. Ignoring them costs hours, every time.

- [The app runs the engine copy inside the bundle](.claude/procedures/app-runs-from-the-bundle.md) — when a fix seems to have no effect, suspect the bundle before the fix
- [One HID handle at a time, no unsolicited reports on macOS](.claude/procedures/one-hid-handle.md) — quit the app before probing; ask for state, never wait for it
- [A read-back sharing the suspect parameter proves nothing](.claude/procedures/verification-must-not-be-blind.md) — read this before believing any protocol conclusion
- [Profile +/- is emulated by the app, not the firmware](.claude/procedures/profile-step-is-emulated.md) — `51 94` and `51 90` are dead ends, measured as such
- [Remappings persist, live state does not](.claude/procedures/remaps-persist-live-state-does-not.md) — "only works while the app is open" usually means this

## Common commands

```bash
swift build --package-path ControlPadGUI          # compile the GUI
swift test  --package-path ControlPadGUI          # Swift tests
python3 -m pytest ControlPadEngine/tests          # engine tests
./ControlPadGUI/scripts/make_app_bundle.sh        # rebuild + sign + install the app
```

Use the `rebuild-app` skill rather than the bare script when the point is to see
a change in the running app: it also quits the old instance, which otherwise
holds the device.

## Conventions

- **Code, comments, documentation and commit messages are in English.** Existing
  Italian comments in the engine are legacy; do not add more.
- Commits follow Conventional Commits — CI enforces the PR title format
  (`.github/workflows/pr-checks.yml`).
- Interface text goes into **both** `it.lproj` and `en.lproj` in the same commit;
  Italian keeps its accents. The `localization_parity` hook reports one-sided keys
  after every edit, and the `i18n-sync` skill covers the rest.
- The `.pcapng` captures cannot be re-recorded on macOS: they are the only source
  of the protocol. Writes to them are refused by the `block_captures` hook.

## Carrying knowledge across sessions

A session that rediscovers something the previous one already established is
wasted work. `.claude/procedures/` exists to stop that, and every entry is linked
above, so it is in context from the first turn.

**Record a new procedure** — via the `record-procedure` skill — when all three
hold: it cost more than one attempt; the source does not say it; it will come up
again. Typical shapes: a step order that must be respected, a check that looked
like confirmation and was not, a hardware or OS constraint invisible in the code.

**Do not record**: anything a careful reader would get right from the code (that
is a code comment), a one-off bug and its fix (`git log` has it), anything already
in `README.md`, session-local detail, or anything not actually verified. An
unverified entry is worse than none, because it will be trusted later.

When an entry turns out to be wrong, correct it and move its `verified` date in
the same pass. When the code makes it false, delete it in the commit that changed
the code.
