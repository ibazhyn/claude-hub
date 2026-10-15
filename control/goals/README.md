# control/goals/ — one file per goal

`current-goal-<G>.md`, where `<G>` is the goal id from `python tools/hub.py next-id goal`. The goal file is
the authority on its goal's state and the handoff anchor between sessions: a fresh session resumes from it
and `control/NEXT-SESSION-PROMPT.md`, not from chat history. Open only your own goal's file. Correct wrong
statements **in place** — a correction appended below a wrong sentence leaves the wrong sentence readable.
When a goal is `DONE` for more than a few days, move its file to `archive/` (never delete it).

Template:

```markdown
---
goal: G-YYYYMMDD-NNN
title: <the user's outcome in one line>
status: LIVE | PAUSED | DONE
owner: <session label>
areas: <repository keys and product areas this goal owns>
opened: <ISO>
last_update: <ISO>
---

# <G> — <title>

## Request (verbatim)
> <the user's words, in their language — or the INBOX ids that carry them>

## INBOX rows
- IN-YYYYMMDD-SLUG — <status>

## Sessions
| session | repository | status | commit | QA |
|---|---|---|---|---|
| W001-S001 | <key> | queued / running / done / partial / failed / blocked | <short SHA> | PASS / FAIL / pending |

## Decisions
- <date> — <decision> — <by whom>

## Exposures and corrections
- <a refined instruction an in-flight Session still carries; what its symptom will look like>

## Next step
<exactly one next action, concrete enough for a stranger>

## Log (newest first)
- <time> — <event>

## Incoming from another intake
<!-- Other sessions append problems here that belong to this goal's areas, verbatim with their INBOX id.
     The owning session reads this section at start and between waves and turns each item into a Session. -->
```
