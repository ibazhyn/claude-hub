---
name: hub-intake
description: Turn one or many concrete work requests (any language, rough dictation, screenshots) into INBOX rows, isolated Session MDs and the full execution loop — fresh worker per Session, independent QA, automatic repair, status. Use automatically for every concrete fix, change, feature or investigation request.
---

Follow `orchestration/00_INTAKE_TO_SESSIONS.md`; execution rules are in
`orchestration/01_ORCHESTRATION_PROTOCOL.md`. The loop, in order:

1. **INBOX first.** One row per distinct problem in `control/INBOX.md`, verbatim in the user's language,
   before decomposing and before opening any repository. Ids: `python tools/hub.py next-id inbox --slug <word>`.
   Writing these rows is the first action of the turn: only the `hub.py status --brief` state check comes
   before it — never a repository read, follow-up execution or dispatch, including a pending `SETUP`
   follow-up with its held Sessions and the resume of an earlier goal.
2. **Coordination check.** `python tools/hub.py status` lists LIVE goals with owner and areas. A problem in
   an area a LIVE goal of **another** session owns is handed over: append it verbatim under
   `## Incoming from another intake` in that goal file, mark the row `routed -> <G>`, notify the owning
   session if a session-messaging tool is exposed (ToolSearch: "send_message", "list_sessions",
   "SendMessage"), and carry on with the rest in this same turn. Never pause, never wait for the reply. If
   no LIVE goal owns the area, this session keeps the item.
3. **Load the project layer** (`project/PROJECT_PROFILE.md`, `REPOSITORIES.md`, `INVARIANTS.md`,
   `CONVENTIONS.md`, `OVERRIDES.md`, relevant `GLOSSARY.md` and `LEARNINGS.md`). Repository reality
   outranks all of it.
4. **Decompose.** Live intake: one distinct problem = one Session. Backlog sweep: dedupe, drop what is
   already true, cluster by shared root cause / surface / file set. Resolve the repository per problem;
   ambiguous → ONE question listing candidates; spanning repositories → one Session per repository with
   dependency edges.
5. **Choose the depth.** Precise mode when the user states the cause or fix, or it is proven here: one
   targeted Session. Discovery when the cause is unknown: a bounded recon subagent returns a conclusion
   first. Bulk reading always goes to a fresh subagent, never into this context.
6. **Goal and ids.** New goal: `python tools/hub.py next-id goal`, file
   `control/goals/current-goal-<G>.md` (template in `control/goals/README.md`), a LIVE row in
   `control/OPEN_GOALS.md` with owner label and areas. Wave and Session ids from `hub.py next-id wave` /
   `next-id session --wave W###`.
7. **Write each Session MD** into `tasks/queued/` per `orchestration/02_SESSION_TASK_TEMPLATE.md` — a
   complete prompt a stranger can execute: screenshots transcribed, the standing clause pasted, relevant
   invariants and rulings quoted, acceptance with the locally provable part separated.
8. **Dispatch.** Move each ready MD to `tasks/running/` and start one fresh `hub-session-worker` per Session
   in the background. Different repositories: all in one message. Same repository: one after another,
   unless separate worktrees are explicitly enabled for it in `project/OVERRIDES.md`. A subagent (worker,
   QA, analyst) reporting a command refused for lack of permission means the session is not in Auto mode:
   tell the user once and dispatch in the foreground until it is. Mechanical helpers (file lists, suite runs, diff-vs-criterion
   checks, bookkeeping) may run on a lighter model via the Agent tool's `model` parameter, stated in the
   Session record; the workers, recon, root-cause and QA run on the user's model.
9. **Consume results as they arrive.** Never predict a pending one. Check that the result file exists and
   its header holds up; update the goal file, INBOX and OPEN_GOALS.
10. **QA.** A fresh `hub-qa-reviewer` per Session (or per repository when several Sessions touched it).
    Confirm `results/QA-<SESSION-ID>.md` exists afterwards; if the reviewer could not write it, transcribe
    its returned verdict and mark it as a transcription.
11. **Repair automatically.** FAIL → `python tools/hub.py next-id repair --session <id>` → repair Session MD
    with the failed criteria and QA evidence → fresh worker → fresh QA. Two failed repairs on the same
    criterion → stop and show the user the evidence.
12. **Close.** INBOX rows `done` only after QA PASS — or PARTIAL-VERIFIED where the only unverified leg is
    one the profile says the user verifies (name it in the row's note). Merge LEARNINGS candidates into
    `project/LEARNINGS.md`. When every requested outcome is closed: goal file and `control/OPEN_GOALS.md`
    row `DONE`, the goal's section removed from `control/NEXT-SESSION-PROMPT.md` (`status: EMPTY` restored
    if none remains); otherwise refresh that section. Report in a few lines: completed / running / queued / blocked / needs you.

Between waves, re-read your own goal file's `## Incoming from another intake`.
