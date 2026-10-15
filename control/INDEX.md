# control/ — read this first, then only what your work touches

`control/` holds the hub's ledgers: what the user asked for, which goals are open, what is locked, what was
decided. **Do not read the directory wholesale.** Start with `python tools/hub.py status` — one call
instead of a dozen reads — and open only the files your work touches.

## Always relevant
| file | what | who writes |
|---|---|---|
| `INBOX.md` | every problem the user stated or we discovered, until done or cancelled | orchestrator (rows), on every intake |
| `OPEN_GOALS.md` | register of goals: owner session, areas, `LIVE`/`PAUSED`/`DONE` | orchestrator |
| `NEXT-SESSION-PROMPT.md` | copy-paste prompt for the next session, one section per goal | orchestrator (`hub-handoff`) |
| `hub-config.json` | language, interpreter, write roots, commit regexes, context-budget thresholds | `hub-setup`; `context_budget.py` calibrates its thresholds |

## Per goal and per repository
| path | what |
|---|---|
| `goals/current-goal-<G>.md` | one file per goal — open only your own (template: `goals/README.md`) |
| `locks/TREE_LOCK-<repo-key>.md` | who may edit a repository right now (format: `locks/README.md`) |

## Queues and records
| file | what |
|---|---|
| `DECISIONS.md` | durable decisions: setup, the user's product decisions, orchestration choices |
| `ids.log` | every id `tools/hub.py next-id` allocated — never edit by hand |

## Tooling
- `python tools/hub.py status [--brief]` — configuration, repositories, queues, running work, locks, QA
  worktrees left in `worktrees/`, LIVE goals with owner and areas, inbox, context drift, handoff age.
- `python tools/hub.py next-id goal|wave|session|repair|continuation|inbox …` — collision-free ids.
- `python tools/hub.py context-diff [--json]` — new / changed / removed files in `context/`.
- `python tools/burn.py [DAYS]` — where this hub's tokens went.
- `python tools/guard_test.py` — the safety guard's test suite.

## House rules for writing here
- **Append; never rewrite another context's entries.** Several sessions and workers write here
  concurrently. After every append, re-read the file and confirm your rows are there: two overlapping
  read-modify-writes end last-writer-wins with no error and no trace.
- **A banner that states a condition must say how to check it.** A notice like "nobody may commit to X"
  outlives its facts and keeps stopping work; write the command that proves it still holds.
- **Ids come from `tools/hub.py next-id`**, never from memory or from a "next free" number written anywhere.
- **Never claim a write that did not occur** — re-read the file and see your rows before saying so.
- **Deliverables:** a Session produces one result file (`results/<SESSION-ID>.md`) and QA one report
  (`results/QA-<SESSION-ID>.md`); do not duplicate them into `control/`.
- **Keep ledgers small.** When `INBOX.md` or `DECISIONS.md` grows past `ledger_archive_kb` in
  `hub-config.json` (`hub.py status` warns), move `done`/`cancelled` rows and old decisions to `archive/`
  (moved, never deleted), keeping every open row.
- Hub maintenance (changes to the hub's own engine files) gets no INBOX row, no goal and no Session.
