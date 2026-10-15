---
name: hub-handoff
description: Prepare and announce a handoff to a fresh session — refresh control/NEXT-SESSION-PROMPT.md and the goal file, record durable memory, and announce it loudly at the top of the reply with the prompt pasted inline. Use when the context-budget hook says so, when a goal closes, or when the user ends the day.
---

A handoff the user discovers two hours late is a defect of the hub, not an inconvenience. The user may look
at the screen once an hour.

## 1. Refresh the goal file
`control/goals/current-goal-<G>.md`: what is done (with SHAs and QA verdicts), what is running (which
worker, since when, which result file to watch), what is queued, decisions made, blockers, and the exact
next step. Correct wrong statements **in place** — a correction appended below a wrong sentence leaves the
wrong sentence readable. Update the goal's row in `control/OPEN_GOALS.md` (status `LIVE` → `PAUSED` if
nobody will drive it until the next session; last update).

## 2. Write `control/NEXT-SESSION-PROMPT.md`
A copy-paste-ready prompt addressed to the next orchestrator. It must stand alone:

```
You are the orchestrator of this hub, continuing goal <G> (<one-line subject>).
Read first: control/goals/current-goal-<G>.md, then <the exact files that matter>.
Done: <items with SHAs and QA verdicts>.
Running: <worker / Session id / result file to watch — do NOT dispatch it again>.
Next, in order: <1. … 2. …>.
Blockers / needs the user: <… or none>.
```

Keep one section per goal, newest first, each fenced by `<!-- <G>-BEGIN -->` / `<!-- <G>-END -->`, so
parallel sessions never overwrite each other's section. Re-read the file after writing and confirm your
section is intact. The line `status: EMPTY — no handoff pending.` exists only while the file has no
section: delete it when you add the first one, and put it back when you remove the last. A `SETUP` section
belongs to `hub-setup`'s follow-up; never overwrite it.

## 3. Record memory
Durable conclusions — decisions, root causes, repository facts — go to `project/LEARNINGS.md` or
`control/DECISIONS.md`. If a memory tool is available (Claude's auto memory; the claude-mem plugin when
installed), save the conclusion there too, briefly. Record conclusions, not transcripts.

## 4. Announce — at the TOP of the reply, impossible to miss
In the user's language, first line of the reply, with a visual marker, e.g.:

> 🔴 **NEW SESSION NEEDED** — the prompt is ready: `control/NEXT-SESSION-PROMPT.md`

Then paste the prompt inline so the user does not have to open a file, and one line on what to do: open a
new session in this folder and paste it (or just say "continue").

## Rules
- Keep the prompt current from the middle of every session, not only at the ceiling: refresh it whenever a
  Session lands, a QA verdict arrives or a decision is made.
- Never start new work after announcing a stop-level handoff; finish only the step in hand.
- Running workers are not abandoned by a handoff: their result files land on disk and the next session
  consumes them. Name them, so nobody dispatches them twice.
