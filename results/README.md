# results/ — the record of every Session

| file | written by | format |
|---|---|---|
| `<SESSION-ID>.md` | the worker — skeleton first, filled as it goes | `orchestration/03_RESULT_TEMPLATE.md` |
| `<SESSION-ID>-A02.md`, `-R01.md` | continuation and repair workers | same |
| `QA-<SESSION-ID>.md` | the QA reviewer — skeleton first, rewritten per criterion | `orchestration/06_QA_AND_REPAIR.md` |
| `<SESSION-ID>-salvage.patch` | the orchestrator, before a continuation is dispatched over a stopped worker's uncommitted work | `git diff` output |
| `<SESSION-ID>-collision.md` | a worker that found its result path already taken | explains the id collision |

Rules:
- **Never overwrite another Session's file.** Check that the path does not exist before creating it; a name
  clash is an id collision to report, not an obstacle. Move files with `mv -n`.
- The result file is what connects a Session to its commit: it carries the Session id and the full SHA, so
  git never needs our ids.
- A verdict that exists only in a chat reply is lost at the next handoff: after every QA pass the
  orchestrator confirms `QA-<SESSION-ID>.md` exists.
- Results are history: old ones may be moved to `archive/` (never deleted) once their goal is `DONE`.
