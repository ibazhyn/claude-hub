# Contributing

- Keep the engine project-agnostic: nothing about a specific product, person or machine in `CLAUDE.md`, `.claude/`, `orchestration/`, `tools/`.
- Ship state folders (`project/`, `control/`, `tasks/`, `results/`) as empty templates only.
- Changing the safety guard? Add cases to `tools/guard_cases.json` and run `python tools/guard_test.py` — all must pass.
- One focused change per PR, conventional commit subjects (`fix(guard): …`).
- Never commit real tokens, emails or absolute personal paths.
