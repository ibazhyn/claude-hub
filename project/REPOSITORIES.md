# Repository registry

> Owned by `hub-setup` (`orchestration/05_SETUP_PROTOCOL.md` § Step 4). One `## <key>` section per
> repository. The orchestrator resolves each problem to a repository through the key, the aliases and the
> purpose; workers read their repository's section before the first edit. `tools/hub.py` parses the
> `- path:` and `- working_branch:` lines, so keep the `- field: value` shape with nothing after the value.
>
> `verified: no` on a command means it was detected from a file, never run. The first Session that needs
> it runs it, and records what really works in `project/LEARNINGS.md`.

_No repositories registered yet. The first conversation registers them._

<!--
Record format (an example, not a real record):

## shop-api
- aliases: api, backend, server
- path: C:\Projects\shop-api
- purpose: REST API of the online shop
- working_branch: main
- default_branch: main
- remote: https://github.com/example/shop-api.git
- vcs: git
- stack: Node 20, TypeScript, PostgreSQL
- package_manager: pnpm
- commands:
  - install: pnpm install --frozen-lockfile [package.json + pnpm-lock.yaml; verified: no]
  - build: pnpm build [package.json scripts.build; verified: no]
  - test: pnpm test [package.json scripts.test; verified: no]
  - lint: pnpm lint [package.json scripts.lint; verified: no]
  - typecheck: pnpm typecheck [package.json scripts.typecheck; verified: no]
  - e2e: none detected
- instruction_files: CLAUDE.md, CONTRIBUTING.md
- commit_convention: conventional, 27 of 30 subjects, e.g. "fix(cart): totals round half up"
- identity: dana@example.com
- push_policy: never
- dirty_at_setup: 3 files, pre-existing, the user's
- notes: monorepo with packages/api and packages/shared

Field notes:
- path: absolute, as the OS writes it (on macOS/Linux ~/projects/shop-api is also fine).
- purpose: the user's words; "inferred from README" when setup derived it.
- vcs: git, or none for a folder that is not a git repository (no commits there).
- push_policy: never (default) or on request - orchestration/04_GIT_SAFETY_AND_COMMITS.md, Pushing.
- commands: each with the file it was detected from and verified: no until a Session runs it.
-->
