# Invariants

> What must stay true in every change. Checked in full by every worker and every QA pass whenever a change
> touches them, however small the diff. Session MDs quote the ones that apply, by id.
>
> **Baseline B1–B8** ship with the hub as defaults: they hold for almost every product. The user may
> override one for a project — the override goes into `project/OVERRIDES.md` (dated, verbatim) and is
> noted below the item. **Project invariants P1…** are written by `hub-context-analyst` from `context/`
> and the repositories' docs, each with its source.

## Baseline engineering invariants (defaults — the user may override)

- **B1 — No fabricated data presented as real.** No mock, seed, demo, placeholder or invented records in
  product paths, and no automatic re-seeding. Test fixtures live in tests.
  *Breaks:* users act on data that does not exist; defects hide behind plausible screens.
- **B2 — Persisted state survives reload and navigation.** What the user saved is read back from the
  authoritative store, not from memory or browser state.
  *Breaks:* work silently lost on refresh.
- **B3 — Deleted stays deleted.** Nothing resurrects a deleted record: no cache, re-sync, retry or seed.
  *Breaks:* trust, and sometimes compliance.
- **B4 — One authoritative read/write source.** No shadow client-side copy substituting for the real
  store; one write path per piece of state.
  *Breaks:* two truths that drift apart.
- **B5 — Authorization is enforced server-side.** UI visibility is not authorization; a hidden button is
  not a permission check.
  *Breaks:* any caller can do what the UI merely hides.
- **B6 — Tenant, role and record-scope boundaries are preserved.** A change never widens who can read or
  write what, and never mixes one tenant's or user's data into another's.
  *Breaks:* data leaks across customers.
- **B7 — Nothing is hardcoded per user, role, tenant, department or customer.** Behaviour comes from data,
  configuration or the permission model.
  *Breaks:* the next customer, role or user gets the wrong behaviour.
- **B8 — Shared contracts are changed only after tracing every consumer.** APIs, schemas, shared components
  and events: find every consumer (including embedded or standalone variants) before changing them.
  *Breaks:* a fix in one place breaks two others.

## Project invariants

_None yet — written by `hub-context-analyst` at setup._

Format:
- **P1 — <rule>.** Why it exists. *Breaks:* what goes wrong if violated. *Source:* `context/<file> § <heading>`.

## Overrides of the baseline

_None._
