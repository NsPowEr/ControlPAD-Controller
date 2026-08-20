---
name: i18n-sync
description: Compare the it.lproj and en.lproj localizations of the GUI to find missing keys, orphan keys, and keys referenced in Swift but never defined. Use after adding or renaming interface text, or when a raw key shows up on screen instead of a translation.
---

# Keeping the it/en localizations in sync

The GUI ships in two languages with English as the default
(`defaultLocalization: "en"` in `Package.swift`). Both catalogs are maintained by
hand:

- `ControlPadGUI/Sources/ControlPadGUI/Resources/it.lproj/Localizable.strings`
- `ControlPadGUI/Sources/ControlPadGUI/Resources/en.lproj/Localizable.strings`

A key present in only one catalog does not break the build. It shows up at
runtime as a raw key on screen, and only in the neglected language — which is
why it usually ships unnoticed.

The `localization_parity` hook reports one-sided keys automatically after every
edit. Use this skill for the checks the hook does not perform.

## 1. Keys present on one side only

```bash
cd ControlPadGUI/Sources/ControlPadGUI/Resources
keys() { grep -oE '^[[:space:]]*"[^"]+"[[:space:]]*=' "$1" | grep -oE '"[^"]+"' | sort -u; }
echo "--- only in it.lproj ---"
comm -23 <(keys it.lproj/Localizable.strings) <(keys en.lproj/Localizable.strings)
echo "--- only in en.lproj ---"
comm -13 <(keys it.lproj/Localizable.strings) <(keys en.lproj/Localizable.strings)
```

## 2. Keys used in code but never defined

Strings go through `Localization.swift`. Extract the keys referenced in the views
and compare them against the defined ones:

```bash
cd ControlPadGUI/Sources/ControlPadGUI
grep -rhoE '"[a-z][a-zA-Z0-9_]*(\.[a-zA-Z0-9_]+)+"' Views/ Models/ | sort -u > /tmp/used.txt
grep -oE '^[[:space:]]*"[^"]+"[[:space:]]*=' Resources/en.lproj/Localizable.strings \
  | grep -oE '"[^"]+"' | sort -u > /tmp/defined.txt
comm -23 /tmp/used.txt /tmp/defined.txt
```

The first command also catches identifiers that are not localization keys at all
(effect ids, bridge command names). Read the output and discard those — it is not
a ready-made list of defects.

## 3. Keys defined but never used

Invert the comparison (`comm -13`) to find orphans left behind by a removal.
Before deleting one, check that it is not assembled at runtime by concatenation,
or a string that is still needed disappears.

## Rules when writing text

- A new key goes into **both** catalogs in the same commit.
- Italian must carry its accents (`è`, `più`, `perché`); never substitute ASCII
  lookalikes.
- Format specifiers (`%@`, `%d`) must appear the same number of times in both
  languages, otherwise formatting crashes at runtime in one language only.
