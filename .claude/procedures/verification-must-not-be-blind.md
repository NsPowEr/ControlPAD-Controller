---
title: A read-back that shares the suspect parameter with the write proves nothing
verified: 2026-08-20
applies-to: any protocol claim about the device, any read-back check
---

## What is true

On this project a verification by read-back is only worth something if it does
**not** share with the write the very parameter that might be wrong.

## Why it bites

On 2026-08-20 the four indicator LEDs were "proven" to be a global register:
red was written with the pad on bank 3 and read back from bank 7, red came back,
therefore global. They are in fact 24 slots, one per bank — but read and write
both used the same fixed address `0x00fc`, the bank 1 slot in both cases. The
check was exactly as blind as the code it was meant to test, so it always agreed.
Three further hypotheses were built on that false conclusion, all dead ends.

The same mistake in subtler form with `0x0028`: the value `17 04 08` was
consistent both with the indices of the two keys being hunted and with
`[lighting slot, speed]`. The convenient reading was chosen instead of looking
for the datum that separated them — it was enough to notice that `0x0028` stayed
`17 04 08` even after the profile keys had been cleared.

## What to do

Before believing a read-back, ask **which variable it is using** and whether it
is the same one the write used. If it is, the check does not discriminate: make
that variable vary, or compare against an independent source (a capture, or
observed physical behaviour).

When two readings of a datum are both plausible, look for the case that
separates them instead of picking one.

## What does not prove anything

Agreement between a write and a read that share an address, an index, or a bank
selector. Also: a test that measures a global, sticky assignment left behind by
an earlier run — that is how the profile-step direction ended up inverted in the
code.
