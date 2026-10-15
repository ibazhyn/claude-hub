# INBOX — every problem the user stated, and every problem we found, until it is finished

Nothing the user says may exist only in a chat transcript. **Every distinct problem gets a row here the
moment it is heard — verbatim, in the user's language — before decomposition and before any repository is
opened.** Problems discovered mid-flight (by the orchestrator, a worker's result or a QA finding) get rows
too, with the discoverer in the note: a real defect noticed in passing is executed, not merely mentioned.

A row leaves the open set only as `done` (implemented **and** QA-verified) or `cancelled` (the user withdrew
it, with the user's words in the note). Silence never closes a row.

## Statuses
| status | meaning |
|---|---|
| `unrouted` | recorded, owner not decided. Must not survive the intake turn. |
| `held` | waiting for setup or for the user's answer; the reason is in the note. |
| `session` | a Session MD exists (queued, running or in QA). |
| `routed -> <G>` | handed to goal `<G>`, owned by another live session; the target goal file carries it under `## Incoming from another intake`. This session does not wait for it. |
| `done` | implemented and QA-verified. Only then. A leg that only the user can verify (the profile's *cannot be verified locally*) is named in the note: "verified by the user on <environment>: <what>". |
| `cancelled` | the user withdrew it. |

Status values are written in backticks so `tools/hub.py` can count them. Ids come from
`python tools/hub.py next-id inbox --slug <word>`. Procedure: `orchestration/00_INTAKE_TO_SESSIONS.md`.

## Rows

| id | received | user's words (verbatim) | repo | status | goal / session | note |
|---|---|---|---|---|---|---|
