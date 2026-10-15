# 00 — Intake → Sessions

The mandatory behaviour when the user gives the orchestrator concrete work. Skill: `hub-intake`.

## 1. Intake means action
The user may dictate roughly, self-correct mid-sentence, attach screenshots and mix one to ten or more
unrelated problems in one message, in any language. A concrete problem the user wants fixed means ACTION:
do not stop at a summary, and never ask the user to request a prompt, a plan or a task file separately.

## 2. The INBOX row comes first
Before decomposing and before opening any repository, write one row per distinct problem into
`control/INBOX.md`. It is the first action of the turn — only the `hub.py status --brief` state check
precedes it; no repository read, follow-up execution or dispatch comes first, a pending `SETUP` follow-up
included:

| column | content |
|---|---|
| id | `IN-YYYYMMDD-SLUG` from `python tools/hub.py next-id inbox --slug <word>` |
| received | local date and time |
| user's words | verbatim, in the user's language — never paraphrased; a screenshot is summarized in words here and transcribed fully into the Session MD |
| repo | repository key, or `?` until resolved |
| status | `unrouted` · `held` · `session` · `routed -> <G>` · `done` · `cancelled` |
| goal / session | the goal id and Session id(s) carrying it |
| note | anything that explains the status (why held, who cancelled, where routed) |

Statuses:
- `unrouted` — recorded, owner not decided. Must not survive the intake turn.
- `held` — waiting for setup or for the user's answer; the reason is in the note.
- `session` — a Session MD exists for it (queued, running or in QA).
- `routed -> <G>` — handed to goal `<G>` owned by another live session (section 7).
- `done` — implemented **and** QA-verified. Only then. A leg that only the user can verify (the profile's
  *cannot be verified locally*) is named in the note instead of holding the row open.
- `cancelled` — the user withdrew it; the user's words in the note.

Problems discovered mid-flight — by you, a worker's result or a QA finding — get rows too, with the
discoverer named in the note. "Noticed and mentioned once" is not a disposition.

## 3. Classify and decompose
1. Enumerate distinct problems P1…Pn. Dedupe exact repeats only.
2. For each: where (screen, endpoint, command), observed, expected, evidence (screenshot transcription,
   error text, logs).
3. Class: `DEFECT`, `FEATURE`, `INVESTIGATION` (a question about the code that needs digging),
   `OPERATIONAL` (local environment or tooling).
4. **Live intake:** one distinct problem = one Session = one fresh worker context. Several screenshots or
   symptoms of the same user-visible defect may stay one Session; split whenever the owner, acceptance,
   workflow, repository or safe implementation context differs.
5. **Backlog sweep** (the user points at an existing pool — a list of known issues, a findings file): dedupe first
   (an item fixed under another id is closed, not re-fixed), drop what unrelated work already made true,
   then cluster by shared root cause, shared surface or shared file set. A cluster is well formed when one
   focused change plausibly satisfies every item and the items touch overlapping files. Each item keeps its
   own traceability in the Session MD.

## 4. Resolve the repository
Match the problem against `project/REPOSITORIES.md` keys, aliases and purpose, and against
`project/GLOSSARY.md` and the profile's module list. If more than one repository fits, ask ONE question
listing the candidates (batched with any other genuine question). A problem that spans repositories becomes
one Session per repository, with `depends_on` edges (for example the API Session before the web Session).

## 5. Precise mode or discovery
- **Precise mode:** the user states the cause or the fix, or the cause is already demonstrated in this hub
  → write one targeted Session with that fix as its GOAL. Do not re-derive known context.
- **Discovery:** intent, cause or blast radius genuinely unknown → dispatch a bounded recon subagent (fresh
  context, read-only) that returns the mechanism with file references, then write the Session from that.
  Precise mode requires proof, not a hunch: an assumed cause gets discovery.

## 6. Load the right knowledge
Before the first decomposition in a session read the project layer: `project/PROJECT_PROFILE.md`,
`REPOSITORIES.md`, `INVARIANTS.md`, `CONVENTIONS.md`, `OVERRIDES.md`, and the parts of `GLOSSARY.md` and
`LEARNINGS.md` that concern the repositories involved. Code, config, tests and git state beat every
document for current facts.

## 7. Another live session may own the area
`python tools/hub.py status` lists LIVE goals with their owner label and areas. If a problem belongs to an
area or repository that a LIVE goal of another session owns, hand it over — procedure in
`01_ORCHESTRATION_PROTOCOL.md` § "Several sessions in one hub" — and continue with the rest in the same
turn. If no live goal owns it, this session keeps it.

## 8. Write the Sessions
- Goal: reuse the current goal of this session when the problems belong to it; otherwise
  `python tools/hub.py next-id goal`, create `control/goals/current-goal-<G>.md` from the template in
  `control/goals/README.md`, and add a `LIVE` row to `control/OPEN_GOALS.md` with your owner label and the
  areas/repositories.
- Wave: `python tools/hub.py next-id wave`. Sessions: `python tools/hub.py next-id session --wave W###`.
  A wave groups Sessions dispatched together; create a new wave only for real dependency ordering.
- Each Session MD goes to `tasks/queued/<SESSION-ID>-<short-slug>.md`, written to
  `02_SESSION_TASK_TEMPLATE.md`. It must let a fresh worker execute without the chat: transcribe every
  screenshot (visible state, exact texts, numbers, error messages, which element is wrong).
- Update each INBOX row to `session` with the goal and Session ids.

## 9. Execute
Dispatch, consume results, QA, repair and close exactly as `01_ORCHESTRATION_PROTOCOL.md` and
`06_QA_AND_REPAIR.md` describe. Report status to the user briefly once the dispatch is out, and again when
results change the picture.

## 10. When to ask the user
Only for a genuine product decision, an unavailable credential that cannot be deferred, destructive
ambiguity, or a conflict with human work. Everything the repository can establish, establish yourself.
Batch every question into one message, and keep working on everything that does not depend on the answer.

**Exception — setup.** While the hub is `NOT_CONFIGURED`, the setup question (`05_SETUP_PROTOCOL.md`
Step 2) is the whole reply and ends the turn: nothing but setup's Steps 0–1 runs before the answer — no
settings or hook writes, no self-tests, no analysts, no writes to `project/`. That rule overrides this
section.
