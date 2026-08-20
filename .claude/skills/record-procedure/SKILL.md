---
name: record-procedure
description: Record a hard-won procedure or trap in .claude/procedures/ so it is not rediscovered from scratch in a later session, and decide whether something is actually worth recording. Use right after finding out that a task must be done in one specific order, that a check was misleading, or that an obvious approach silently does not work.
---

# Recording a procedure

This project talks to real hardware through a reverse-engineered protocol. Some
facts cost several attempts to establish and are invisible in the source: the
next session will pay that cost again unless the fact is written down where it
gets loaded automatically.

`.claude/procedures/` is that place. `CLAUDE.md` links every entry, so each entry
is visible from the first turn of every session.

## Decide first: is this worth recording?

Record it when **all three** hold:

1. **It cost more than one attempt.** A wrong turn was taken, or a result was
   believed before turning out to be false.
2. **The source does not say it.** Someone reading the relevant file carefully
   would still get it wrong — because the constraint lives in the hardware, in the
   OS, in the build layout, or in the order of operations.
3. **It will come back.** The same task, or the same class of task, is going to be
   attempted again in a later session.

Do **not** record:

- Anything a reader would get right from the code itself. That belongs in a
  comment next to the code, not here.
- A one-off bug and its fix. `git log` already holds that.
- Facts already in `README.md` or `CONTRIBUTING.md`. Link them instead.
- Anything that only matters inside the current session (file paths being edited,
  what is left to do). That is not a procedure.
- A guess, or something believed but not verified. An unverified entry is worse
  than no entry: it will be trusted later. Verify first, then record.

When only some of the three hold, prefer a comment in the code over an entry here.

## How to write the entry

One procedure per file, `kebab-case.md`, in `.claude/procedures/`:

```markdown
---
title: <short imperative or claim>
verified: <YYYY-MM-DD>
applies-to: <files, commands, or the part of the system this governs>
---

## What is true

<The fact, stated flatly. Absolute dates, never "yesterday" or "recently".>

## Why it bites

<What appears to happen if the fact is ignored — the misleading symptom, not the
internal explanation. This is what makes the entry recognizable next time.>

## What to do

<The steps, in the order that works.>

## What does not prove anything

<Checks that look like confirmation but are not. Omit only if there are none.>
```

Then add one line to the index in `CLAUDE.md`, under **Verified procedures**:
`- [Title](.claude/procedures/file.md) — <hook that says when it matters>`

The hook matters more than the title: it is what makes a future session open the
file at the right moment rather than after the mistake.

## Keeping entries honest

Before relying on an entry, check that what it names still exists — a file, a
flag, a command. An entry describes what was true on its `verified` date.

When an entry turns out to be wrong, correct it and move the `verified` date.
Do not leave both versions standing; a contradicted procedure stops being read.
When a fact becomes false because the code changed, delete the entry in the same
commit that changed the code.
