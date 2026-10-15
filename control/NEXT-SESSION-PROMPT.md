# NEXT SESSION PROMPT

> A copy-paste-ready prompt for a fresh session, kept current from the middle of every session (skill
> `hub-handoff`). One section per goal, newest first, fenced by `<!-- <G>-BEGIN -->` and
> `<!-- <G>-END -->` so parallel sessions never overwrite each other. Each section tells the next
> orchestrator what is done, what is running (do not dispatch it again), what is next, which files to read,
> and every blocker. When a goal is finished, delete its section.
>
> A section fenced `<!-- SETUP-BEGIN -->` / `<!-- SETUP-END -->` is `hub-setup`'s follow-up for the first
> guarded session: the next session carries it out without waiting to be asked, right after writing the
> INBOX rows for the user's message (`orchestration/05_SETUP_PROTOCOL.md` § Next session).
>
> The status line below exists only while there is no section: delete it with the first section, restore it
> when the last one is removed.

status: EMPTY — no handoff pending.
