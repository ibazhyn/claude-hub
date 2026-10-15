---
name: hub-setup
description: First-run configuration of this hub (register repositories, ingest context/, generate the project profile, wire hooks and machine settings), its follow-up in the first guarded session, context re-sync, and adding a repository. Use when the profile is NOT_CONFIGURED, when a SETUP follow-up is pending, when context/ drifted from the manifest, or when the user asks to (re)configure, refresh the context ("обнови контекст", "update context") or add a repository.
---

Follow `orchestration/05_SETUP_PROTOCOL.md` exactly. This is the checklist; the protocol has the commands,
the formats and the reasons. The setup session edits only hub files — never product code.

## First run (profile `status: NOT_CONFIGURED`)
> **The first reply asks and stops.** If step 2 has to ask, that question is the whole reply: send it and
> **end the turn**. Until the user answers, only steps 0–1 run — no settings or hook writes, no self-tests,
> no `hub-context-analyst`, no writes to `project/` or `control/NEXT-SESSION-PROMPT.md`, no reading or
> listing outside this folder. This overrides the generic "keep working on everything that does not
> depend on the answer" in `orchestration/00_INTAKE_TO_SESSIONS.md` §10. Steps 3–9 run in the turn that
> brings the answer.

0. **Keep the first message.** Tasks in it go to `control/INBOX.md` now, verbatim, status `held` (waiting
   for setup): setup turns them into Session MDs (step 7), the next session dispatches them before any new
   work (after writing the INBOX rows for its own first message).
1. **Detect, silently:** OS; a working Python ≥ 3.8 (`py -3` / `python` / `python3` — a command that prints
   nothing is not Python); git and the global identity; the files in `context/` (names and sizes only —
   `python tools/hub.py context-diff --json`); whether the first message already names repositories;
   folders already granted to this session (`--add-dir`, the Desktop folder picker) — paths only.
2. **Ask at most ONE batched message**, in the user's language, only for what is missing: the repositories
   (short name + absolute path + optionally what each is, one per line) — a folder already granted to the
   session is proposed ("I can see `<path>` — is this one of your repositories?"), never registered
   without the answer; the context files found, inviting more. State the defaults instead of asking: local
   commits on the current branch, never pushed, the machine's git identity, replies in the user's
   language. The reply is short — a one-line greeting, the question, the context files, the defaults — and
   then the turn **ends**. Skip the question entirely if the repositories were already named.
3. **Validate each path and grant access before reading inside it:** expand `~`; `git rev-parse
   --show-toplevel` (a missing path → ask again for that one only; an existing non-git folder →
   `vcs: none`); a directory-access tool if one is exposed (ToolSearch "request_directory"); merge the paths
   into `.claude/settings.local.json` → `permissions.additionalDirectories`; warn once that Claude may ask to
   approve the settings write. A refused write never stalls setup — it becomes a follow-up item.
4. **Register each repository** in `project/REPOSITORIES.md` with every field of its record format,
   including the per-repository `identity`, the observed commit convention and `verified: no` commands.
   Setup never runs install, build or test. Unreadable fields → `pending` + a `repo-docs` follow-up item.
5. **Ingest context:** re-run `context-diff --json` (the user may have added files), then dispatch
   `hub-context-analyst` in mode `full` (several `partial` analysts plus a `merge` pass over ~400 KB). It
   writes the project layer and returns at most 40 lines. Never read the raw files yourself.
6. **Wire the machine:** hooks into `.claude/settings.local.json` with the detected interpreter, in the
   protocol's exact shape; verify (a sample `git reset --hard` payload comes back denied,
   `python tools/guard_test.py` passes, `python .claude/hooks/context_budget.py --selftest` and `python .claude/hooks/session_relay.py --selftest` pass); fill
   `control/hub-config.json` (language, python command, write roots, commit subject regex that always
   includes the conventional form). No Python → hooks stay off; say so plainly; the contract still binds.
7. **Held tasks:** goal file and `OPEN_GOALS.md` row `PAUSED`, owner `setup` + Session MDs now
   (`hub-intake` up to the MDs). No dispatch in the setup session — unless the user insists on starting now
   (protocol Step 9: take over the goal, tick what is dispatched).
8. **Record — the last writes of setup:** profile front matter `CONFIGURED` + `configured_at`; a line in
   `control/DECISIONS.md`; then the `SETUP` follow-up section in
   `control/NEXT-SESSION-PROMPT.md`, written **once, from the final state** — first "confirm the guard is
   live", then any refused settings write with its complete JSON, `repo-docs` items, `missing` identities,
   the held Session MDs by path. No placeholder may remain and every `json` block must parse:
   `python tools/hub.py status --brief` must not print `SETUP SECTION BROKEN`.
9. **Confirm** in at most 12 lines: repositories (name → path, branch), context ingested (N files), the
   3–5 most important invariants, the defaults, genuine open questions only, a refused settings write as
   exactly what to approve, and: open a **new session** and write "continue" (or a new task) — the guards
   and repository access load there, held tasks start by themselves; from then on, just dictate.

## Next session — the `SETUP` follow-up
`hub.py status --brief` prints `SETUP FOLLOW-UP PENDING`: do it without waiting to be asked, right after the
INBOX rows for the user's message (those are always the first action of the turn).
1. Probe the guard: `git commit --dry-run -m wip` must be denied by "hub safety guard". A settings write
   still pending → retry it now: approved → keep the section, dispatch nothing, ask once for one more
   session; declined → say exactly what to approve (writing `.claude/settings.local.json` and what it adds)
   instead of asking for another session. Not denied and nothing pending → check the hooks
   (protocol, Troubleshooting). Without Python, skip this gate and say so.
2. Take over the setup goal (`LIVE`, owner = this session) only while its owner is `setup` or its owner
   session is verifiably gone; run the `repo-docs` items; re-read `missing` identities.
3. Dispatch the held Sessions not ticked yet; tick each item; delete the section when every item is done.

## Re-sync ("обнови контекст", "update context", or drift at conversation start)
`python tools/hub.py context-diff --json` → `hub-context-analyst` in mode `delta` over the new, changed and
removed files only → it updates the affected `project/*.md` and the manifest. Never touch the user's
content in `project/OVERRIDES.md`. Report in one line.

## Add a repository ("добавь репозиторий X, путь Y", "add repository X at Y")
Steps 3 and 4 for that repository, its `write_roots` and commit regex in `control/hub-config.json`, then
`hub-context-analyst` in mode `repo-docs <key>` (or a `SETUP` follow-up item if access is not live yet).

## Reconfigure
Re-run detection, show the current configuration in a few lines, ask only about what the user wants to
change, keep everything else. If Python appeared since setup, run Step 6 now.
