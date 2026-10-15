---
id: W001-S001
repo: api
state: queued
inbox: I-001
---
# Cart total rounds half-even instead of half-up

## Problem
Totals like 10.005 show 10.00; business rule is half-up to the cent.

## Scope
`src/cart/total.*` and its tests only.

## Acceptance criteria
1. 10.005 → 10.01, 10.004 → 10.00 (new unit tests).
2. Existing cart tests stay green.
3. One local conventional commit; no push.

## Guardrails
- No changes to currency formatting elsewhere.
