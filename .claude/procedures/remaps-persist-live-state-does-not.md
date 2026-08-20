---
title: Remappings are permanent; what the app applies live is volatile
verified: 2026-08-20
applies-to: ControlPadEngine/session.py, lighting and mapping features
---

## What is true

Two behaviours that the code alone does not tell apart:

- **Remappings written into a bank are permanent.** They survive unplugging the
  cable with the app closed.
- **What the app applies live is volatile.** The pad drops it as soon as it
  reloads the bank.

## Why it bites

A user reporting "it only works while the app is open" is describing this
difference, not a dependency on the app being open. Chasing the app lifecycle —
process teardown, handle release, launch order — is the wrong direction and
costs a full round of testing.

## What to do

When a setting is expected to survive, write it into the bank as part of a write
session rather than applying it live. To tell the two cases apart in a test,
make the pad reload the bank (switch profile and come back) rather than closing
the app.

## What does not prove anything

Checking that a setting is still in effect while the app is open and the bank has
not been reloaded. Both the persistent and the volatile case look identical
there.
