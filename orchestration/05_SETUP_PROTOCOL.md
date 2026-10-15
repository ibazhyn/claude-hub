# 05 — Setup protocol: first run, context re-sync, adding a repository

Skill: `hub-setup`. Setup makes the hub configure itself on its first conversation: it learns which
repositories exist and where, ingests the user's `context/` once, generates the project layer, and wires
the machine-specific settings. From then on the user only dictates tasks.

Triggers: `status: NOT_CONFIGURED` in `project/PROJECT_PROFILE.md`; the user asks to (re)configure, add a
repository or refresh the context; context drift found by the state check.

In the commands below `<py>` is the detected interpreter (`python3`, `python` or `py -3`) and `<hub>` the
absolute path of this folder. Hooks and folder access load when a session starts, so the setup session
itself runs unguarded: it edits only hub files and never product code. Product work starts in the next
session, automatically, through the `SETUP` follow-up (Step 8 and "Next session" below).

> **The first reply asks and stops.** When Step 2 has a question, that question is the whole reply and the
> turn ends with it. Until the user answers, only Steps 0–1 run — details in Step 2.

---

## Step 0 — keep the first message
If the first message already contains tasks, write each to `control/INBOX.md` at once, verbatim, status
`held`, note "waiting for setup". They are held, not lost: setup turns them into Session MDs (Step 7) and
the next session dispatches them before any new work ("Next session"). Setup never swallows a request.

## Step 1 — detect, silently and cheaply
| what | how |
|---|---|
| OS | from the environment; else `<py> -c "import platform; print(platform.system())"` |
| Python ≥ 3.8 | Windows: try `py -3 --version`, `python --version`, `python3 --version`; macOS/Linux: `python3 --version`, `python --version`. Accept only output matching `Python 3.<minor>` with minor ≥ 8. A command that prints nothing or opens a store page is not Python. |
| git | `git --version`; `git config --global user.name`; `git config --global user.email` |
| context files | `<py> tools/hub.py context-diff --json` (names, bytes, sha256). Without Python: list `context/` with sizes ("Without Python" below). Do not read contents yet. |
| repositories in the first message | lines like `name — path — purpose`, or any absolute paths |
| folders already granted to this session | the additional working directories the environment lists (added with `--add-dir` or the Desktop folder picker). Note the paths only: do not read inside them, and never register one before the user confirms it (Step 2) |

## Step 2 — ask at most ONE batched message, only for what is missing — then end the turn
In the user's language. Content:
1. **Repositories** (required unless the first message named them): "Which repositories should I work
   with? One per line: short name — absolute path — (optional) what it is." Give the example
   `api — C:\Projects\shop-api — backend` or `api — ~/projects/shop-api — backend`, matching the OS.
   Folders already granted to this session (Step 1) are **proposed, never registered silently**: "I can
   see `<path>` — is this one of your repositories? If so, give it a short name."
2. **Context files found:** list them (name, size). Invite more before answering: anything about the
   product, architecture, rules, what must never break, how to test, environments.
3. **Defaults, stated, not asked:** commits are local on the current branch, never pushed, authored by
   `<git name> <git email>`, replies in <language>.
4. **Git identity missing** (no global identity)? Say so and give the user the two commands to run in a
   terminal — `git config --global user.name "Your Name"` and `git config --global user.email
   "you@example.com"` — because the guard never lets Claude set an identity. A repository with its own
   identity (Step 4) can commit meanwhile; others cannot until it exists.

If the first message already named the repositories with valid paths, skip the question entirely (a
folder merely granted to the session is not named: it is proposed in the question).

**Asking ends the turn.** The question is the whole reply; send it and stop. Until the user answers, only
Steps 0–1 run: no settings or hook writes, no self-tests (`guard_test.py`, `--selftest`, sample
payloads), no `hub-context-analyst` dispatch, no writes to `project/` or `control/NEXT-SESSION-PROMPT.md`,
no reading or listing outside the hub folder. This overrides the generic rule of
`00_INTAKE_TO_SESSIONS.md` §10 ("keep working on everything that does not depend on the answer"): in
setup, every later step depends on the answer. Keep the reply short — a one-line greeting, the question,
the context files found, the defaults, and (only when the first message held tasks) one line saying they
are recorded and start after setup. Steps 3–9 run in the turn that brings the answer.

## Step 3 — validate each path and grant access (before reading anything inside it)
1. **Expand `~`** to the absolute home path first — a quoted `"~/x"` is not expanded by any shell — and
   work with the absolute path from here on.
2. **Validate:** `git -C "<path>" rev-parse --show-toplevel` succeeds → use the top level it prints. A path
   that does not exist → ask again, for that repository only, and carry on with the rest meanwhile. A
   folder that exists but is not a git repository → `vcs: none` (Sessions there can edit and verify but
   cannot commit; the result lists changed files instead) — say so in the confirmation, and never run
   `git init` in the user's folder yourself.
3. **Access now:** if a directory-access tool is exposed at runtime (ToolSearch "request_directory" or
   "directory access"), call it for each path so this session can read the repository.
4. **Access for later sessions:** merge the paths into `.claude/settings.local.json` →
   `permissions.additionalDirectories` — read the file if it exists, keep every other key and entry, add
   without duplicates, write, and re-read it to confirm valid JSON
   (`<py> -c "import json; json.load(open('.claude/settings.local.json', encoding='utf-8'))"`). Warn the
   user once that Claude may ask to approve writing the settings file.
5. **A refused write** (declined, or nobody can approve it in a non-interactive run) never stalls setup:
   finish the rest, keep the exact JSON for the `SETUP` follow-up (written in Step 8), and say so plainly.

## Step 4 — register each repository in `project/REPOSITORIES.md`
Read-only commands; setup never runs install, build or test. Follow the record format in that file, one
`- field: value` per line with nothing after the value. If the repository's files cannot be read yet (no
access in this session), register what git reveals, write `pending` for the rest, and add a `repo-docs`
item to the `SETUP` follow-up.

| field | source |
|---|---|
| key | short kebab-case from the user's name for it (`shop-api`); unique |
| aliases | the user's word for it, the folder name, obvious synonyms (backend, фронт, admin…) |
| path | the absolute top level, as the OS writes it |
| purpose | the user's description, else the README's first paragraph ("inferred from README") |
| vcs | `git`, or `none` (Step 3) |
| working_branch | `git -C <p> rev-parse --abbrev-ref HEAD` |
| default_branch | `git -C <p> symbolic-ref --short refs/remotes/origin/HEAD` minus `origin/`, else `unknown` |
| remote | `git -C <p> remote get-url origin` with credentials stripped (`https://user:token@host/x` → `https://host/x`) |
| stack, package_manager, commands | the detection table below; each command with the file it came from and `verified: no` |
| instruction_files | `CLAUDE.md`, `AGENTS.md`, `CONTRIBUTING.md`, `.cursorrules`, `.github/copilot-instructions.md`, nested `CLAUDE.md` files — workers must read and obey them |
| commit_convention | `git -C <p> log -30 --format=%s` → classification below, with the regex and three example subjects |
| identity | `git -C <p> config user.email` — the effective identity for this repository (repository config can differ from global). Workers compare against this field. None yet → `missing`, plus a `SETUP` item "re-read the identity of <key>" (the user sets it, Step 2). |
| push_policy | `never` (default) or `on request` — `04_GIT_SAFETY_AND_COMMITS.md` § Pushing |
| dirty_at_setup | `git -C <p> status --porcelain` line count — pre-existing changes belong to the user |
| notes | monorepo layout, submodules, LFS, anything unusual |

**Command detection** (read manifests only; the CI workflow is the most trustworthy source):
| file | stack / package manager | commands |
|---|---|---|
| `package.json` + `pnpm-lock.yaml` / `yarn.lock` / `bun.lock*` / `package-lock.json` | Node; pnpm / yarn / bun / npm | `scripts`: test, build, lint, typecheck (`typecheck`, `type-check`, `tsc`), e2e (`e2e`, `test:e2e`, playwright, cypress); install per lockfile |
| `pyproject.toml`, `setup.cfg`, `requirements*.txt`, `Pipfile`, `poetry.lock`, `uv.lock` | Python; pip / poetry / uv / pipenv | pytest only when it is configured (`pytest.ini`, `[tool.pytest.ini_options]` in `pyproject.toml`, `[tool:pytest]` in `setup.cfg`, `conftest.py`) or imported by the tests (`import pytest`); otherwise `python -m unittest` — a `tests/` folder alone is not pytest. ruff / flake8, mypy / pyright when configured |
| `tox.ini` | Python | `tox` |
| `go.mod` | Go | `go build ./...`, `go test ./...`, `go vet ./...` |
| `Cargo.toml` | Rust | `cargo build`, `cargo test`, `cargo clippy` |
| `pom.xml` / `build.gradle(.kts)` | Java/Kotlin; Maven / Gradle | `mvn test`, `mvn package` / `./gradlew test`, `./gradlew build` |
| `*.sln`, `*.csproj` | .NET | `dotnet build`, `dotnet test` |
| `Gemfile`, `composer.json` | Ruby / PHP | `bundle exec rspec` or `rake test` / `vendor/bin/phpunit` |
| `Makefile` | any | targets `test`, `build`, `lint` |
| `docker-compose*.yml` | services | record, never start |
| `.github/workflows/*.yml` | CI | the commands CI really runs |
| `pnpm-workspace.yaml`, `turbo.json`, `nx.json`, `lerna.json` | monorepo | per-package commands; note it |

Also add the repository's row to `project/CONVENTIONS.md` → *Commit subjects* (repository, observed
convention, regex, examples).

**Commit convention classification** of the 30 subjects:
- `conventional` — at least 60% match `^(feat|fix|refactor|perf|test|docs|chore|build|ci|style|revert)(\([^)]*\))?!?: \S`;
- another clear house style (an id prefix such as `ABC-123: …`, a module prefix, a fixed verb) — derive a
  regex that matches at least 90% of the subjects, test it on them;
- otherwise `none clear` → the contract default (conventional commits).

## Step 5 — ingest the context (`hub-context-analyst`)
- **Re-run `<py> tools/hub.py context-diff --json` first** — Step 2 invited the user to add files.
- Dispatch one `hub-context-analyst` in mode `full` with that file list (paths, bytes, sha256) and the
  registry. It reads the context files fully and, in each readable repository, only top-level orientation
  material (README, docs index, architecture docs, instruction files). It writes
  `project/PROJECT_PROFILE.md` (product summary, modules, architecture, environments, what cannot be
  verified locally, people and roles), `project/INVARIANTS.md` (baseline B1–B8 kept, project invariants
  added), `project/CONVENTIONS.md`, `project/GLOSSARY.md` and `project/CONTEXT_MANIFEST.md`, citing every
  derived statement as `context/<file> § <heading>`. It returns at most 40 lines. The main context never
  reads the raw material.
- Formats: `.md`, `.markdown`, `.txt` preferred; PDF read when possible; anything else listed in the
  manifest as `skipped (format)`.
- Large sets (more than ~400 KB in total): split the files into related groups of at most ~300 KB, dispatch
  one analyst per group in mode `partial <group>` (all in one message; each writes
  `project/_ingest/<group>.md`), then one analyst in mode `merge` that writes the final files and moves the
  partials to `archive/`.
- Conflicts between files are recorded with both sources; ask the user only if one changes how work is
  done. Credentials found in context are never copied into `project/` — tell the user which file holds them.
- A repository the analyst could not read (access not live in this session) is reported; it becomes a
  `repo-docs <key>` item in the `SETUP` follow-up.
- Afterwards `<py> tools/hub.py context-diff` must show no drift.

## Step 6 — wire the machine
**Hooks** go into `.claude/settings.local.json` (merged as in Step 3). `command` is the bare interpreter;
interpreter flags go into `args` before the script; use the OS-native separator after
`${CLAUDE_PROJECT_DIR}`.

Windows, interpreter `py -3`:
```json
{
  "hooks": {
    "UserPromptSubmit": [
      { "hooks": [ { "type": "command", "command": "py",
                     "args": ["-3", "${CLAUDE_PROJECT_DIR}\\.claude\\hooks\\context_budget.py"] } ] }
    ],
    "PreToolUse": [
      { "matcher": "Bash|PowerShell|Write|Edit|NotebookEdit",
        "hooks": [ { "type": "command", "command": "py",
                     "args": ["-3", "${CLAUDE_PROJECT_DIR}\\.claude\\hooks\\safety_guard.py"] } ] }
    ]
  }
}
```
macOS/Linux, interpreter `python3`: the same with `"command": "python3"` and
`"args": ["${CLAUDE_PROJECT_DIR}/.claude/hooks/safety_guard.py"]` (and `context_budget.py` likewise).
Add the autonomous handoff the same way: `session_relay.py` under `"Stop"` (no matcher) and under
`"PreCompact"` with `"matcher": "auto"`. To keep manual handoffs, set `"relay": {"enabled": false}` in
`control/hub-config.json`.

**Verify each hook by piping a sample payload through it.** Write two payload files with the Write tool
into the system temp directory — writing files keeps destructive phrases out of the command line, which a
live guard would otherwise refuse:
- `hub-guard-sample-deny.json`: `{"tool_name": "Bash", "tool_input": {"command": "git reset --hard"}, "cwd": "<hub>"}`
- `hub-guard-sample-allow.json`: the same with `"git status"`.

Then:
1. `<py> .claude/hooks/safety_guard.py < "<temp>/hub-guard-sample-deny.json"` → prints JSON with
   `"permissionDecision": "deny"`; the allow sample prints nothing.
2. `<py> tools/guard_test.py` → every case passes.
3. `<py> .claude/hooks/context_budget.py --selftest` → every scenario PASS.
   `<py> .claude/hooks/session_relay.py --selftest` → every scenario PASS.
4. Delete the two sample files.
A failure here is fixed before setup is reported complete.

**`control/hub-config.json`** — fill: `language`; `python_command` as a list (`["py", "-3"]`,
`["python3"]`); `write_roots` = the hub root plus every repository path (absolute); `commit.subject_regex`
and `commit.subject_regex_source` (where it came from). The conventional form is **always** part of the
regex, because a Session that cannot fill the house style falls back to it:
- conventional or none clear: `^(?:feat|fix|refactor|perf|test|docs|chore|build|ci|style|revert)(?:\([^)]+\))?!?:\s+\S`
- another house style `<h>`: `^(?:<h>|(?:feat|fix|refactor|perf|test|docs|chore|build|ci|style|revert)(?:\([^)]+\))?!?:\s+\S)`
- several repositories with different conventions: one alternation of their bodies.
Leave `context_budget` at its defaults unless the user said the model has a 1M window (then 1000000 with
150000 / 350000 / 400000); the hook also calibrates itself. Re-read the file to confirm valid JSON.

**No Python?** Hooks stay off and `hub.py` is unavailable. Say so plainly in the confirmation: the guards
are not active, the contract still binds, and the hub works from the files ("Without Python" below).
Recommend installing Python 3.8+ and saying "reconfigure" afterwards.

## Step 7 — held tasks
Turn the `held` INBOX rows into a goal and Session MDs now (`hub-intake` up to writing the MDs; rows become
`session`). The goal file and its `control/OPEN_GOALS.md` row are `PAUSED` with owner `setup` — this
overrides `hub-intake`'s `LIVE` default: no session drives the goal until the next one takes it over. Do not
dispatch in the setup session: the guards and folder access load with the next session, which dispatches
these Sessions before any new work. Keep their paths for Step 8.

## Step 8 — record (the last writes of setup)
- `project/PROJECT_PROFILE.md` front matter: `status: CONFIGURED`, `configured_at: <ISO>`, `language`,
  `owner`, `git_identity` (the global identity, or `missing`).
- One line in `control/DECISIONS.md`: setup completed, repositories, defaults.
- The **`SETUP` follow-up** in `control/NEXT-SESSION-PROMPT.md` is written **once, here, from the final
  state**: nothing goes into that file earlier in setup, and the section is not patched afterwards. It is
  fenced `<!-- SETUP-BEGIN -->` / `<!-- SETUP-END -->` (the `status: EMPTY` line removed) and lists, as
  checkboxes, what the first guarded session must do:
  - "confirm the guard is live" (always the first item — "Next session" step 1);
  - retry the settings write (if Step 3 or Step 6 was refused): what it adds, and the complete JSON object
    to merge into `.claude/settings.local.json`, fenced as `json`, with the real absolute paths;
  - `repo-docs <key>` for each repository not read yet (Steps 4–5);
  - "re-read the identity of <key>" for each repository whose `identity` is `missing`;
  - each held Session MD from Step 7, by path, to dispatch.
- **Check the section before Step 9.** No placeholder may remain — no `<…>`, only the real paths and ids of
  this setup — and every `json` block must pass `json.loads`: `<py> tools/hub.py status --brief` prints
  `SETUP FOLLOW-UP PENDING` and must not print `SETUP SECTION BROKEN`. Then read the section once: it
  describes the hub as now configured, with nothing left over from an earlier state. Without Python, check
  the same by reading it.

## Step 9 — confirm
Reply in at most 12 lines, in the user's language:
- repositories: name → path (branch), and any `vcs: none` or pending item;
- context: N files ingested (skipped ones named);
- the 3–5 most important invariants learned (ids);
- the defaults (local commits, never pushed, author, language);
- genuine open questions only;
- a settings write that was refused → exactly what to approve: "in the new session Claude asks once to
  write `.claude/settings.local.json` in this folder (repository access and the guards) — approve it".
  Never a JSON block to copy by hand unless the user asks for one;
- "Open a **new session** in this folder and write «продолжай» / "continue" (or a new task): the guards and
  repository access load there, and <N> held task(s) start by themselves. From then on, just dictate."
If the user carries on in this session instead, remind once that the guards and repository access load
only in a new session. If the user insists on starting now, take over the goal (`LIVE`, this session as
owner), dispatch from the `SETUP` list and tick every dispatched item there, so the next session does not
dispatch it again — the contract binds either way.

## Next session — carrying out the `SETUP` follow-up
The state check (`hub.py status --brief` prints `SETUP FOLLOW-UP PENDING`) makes it the next session's first
work, without waiting for "continue" — right after the INBOX rows for the user's message, which always come
first (`00_INTAKE_TO_SESSIONS.md` §2):
1. **Confirm the guard is live** with a harmless probe that the guard denies: run
   `git commit --dry-run -m wip` from the hub folder. A denial whose reason starts with "hub safety guard"
   means the hooks are loaded; if git answers instead (a dry run changes nothing), they are not.
2. **A pending settings write:** retry it now; the user sees the approval prompt. *Approved* — settings load
   at session start, so it takes effect in the session after this one: keep the section, dispatch nothing,
   and ask once for one more new session. *Declined* — do not ask for another session: say exactly what to
   approve (writing `.claude/settings.local.json` in this folder, and what it adds — access to the named
   repository folders, the guards), or give the section's JSON block if the user prefers to add it by hand;
   keep the section and dispatch nothing until the write has landed. Step 1 found the guard not live and no
   write is pending → check the hooks in `.claude/settings.local.json` (Troubleshooting) before asking for
   a new session. (Without Python the guard can never be live: skip this gate and say so.)
3. Take over the setup goal (`control/OPEN_GOALS.md` row and goal file `LIVE`, owner = this session) —
   but only while its owner is `setup`, or its owner session is verifiably no longer running
   (`01_ORCHESTRATION_PROTOCOL.md` § "Several sessions in one hub", Staleness). A goal another live session
   already drives is not taken over; work for it is handed over as usual.
4. `repo-docs <key>`: finish the repository's record (Step 4) and dispatch `hub-context-analyst` in mode
   `repo-docs <key>` over its top-level docs. Re-read any `missing` identity and record it (still missing →
   remind the user; that repository cannot commit yet).
5. Dispatch the listed Sessions that are not ticked yet (`hub-intake` from its step 8), ticking each.
6. Tick each item as it is done; when every item is done, delete the section (restore `status: EMPTY` if no
   section remains). Report in one line.

---

## Re-sync — "обнови контекст", "update context", or drift at conversation start
1. `<py> tools/hub.py context-diff --json`. No drift → "Context unchanged."
2. Dispatch `hub-context-analyst` in mode `delta` with only the new, changed and removed files. It updates
   the affected statements and manifest rows; statements citing only a removed file are deleted and its row
   marked `removed`. It never touches the user's content in `project/OVERRIDES.md`.
3. `context-diff` again → no drift. Report in one line: what changed and which project files were updated.

## Add a repository — "добавь репозиторий X, путь Y", "add repository X at Y"
Steps 3 and 4 for that repository; `write_roots` and, if its convention differs, `commit.subject_regex` in
`control/hub-config.json`; then `hub-context-analyst` in mode `repo-docs <key>`. If access is not live yet
(no directory-access tool), record the docs pass as a `repo-docs <key>` item in a `SETUP` section and tell
the user that access loads in the next session.

## Reconfigure
Re-run Step 1, show the current configuration in a few lines, ask only about what the user wants to change,
and keep everything else. If Python has appeared since setup, run Step 6 now (hooks, verification,
`python_command`). Never discard the user's rulings, learnings or ledgers.

## Without Python
The hub still works; only the conveniences change:
- **Context hashes** (for `CONTEXT_MANIFEST.md` and drift): PowerShell `Get-FileHash -Algorithm SHA256
  "<file>"`; Windows cmd `certutil -hashfile "<file>" SHA256`; macOS `shasum -a 256 "<file>"`; Linux
  `sha256sum "<file>"`.
- **Ids**: grep `tasks/`, `results/`, `control/goals/`, `control/INBOX.md`, `control/ids.log` and `archive/`
  for the highest id of the kind, take the next one, and append `<ISO time> <id>` to `control/ids.log`
  before using it (`01_ORCHESTRATION_PROTOCOL.md` § Identifiers).
- **Status**: read the profile front matter, `control/OPEN_GOALS.md`, `control/INBOX.md`,
  `control/NEXT-SESSION-PROMPT.md`, and list `tasks/running/` and `control/locks/`.

## Troubleshooting
| symptom | cause and fix |
|---|---|
| guards never fire in a new session | hooks load at session start; check `.claude/settings.local.json` is valid JSON; if the bare interpreter is not on the hook's PATH, use the absolute path from `<py> -c "import sys; print(sys.executable)"` as `command` |
| repositories unreadable | access loads at session start: open a new session; confirm the paths in `permissions.additionalDirectories` |
| background subagents (workers, QA, analysts) stop on permission requests | the session is not in Auto mode; switch to Auto, or the orchestrator dispatches in the foreground |
| a legitimate command is denied | read the reason; the guard names the safe alternative. It is the floor of the contract, not a mistake to route around |
| drift reported every time | a file in `context/` changes on its own (an export, a sync client): move generated files out of `context/` |
