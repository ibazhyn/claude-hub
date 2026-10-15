# archive/ — moved-out history; nothing here is live

What goes here, always by **moving**, never by deleting:
- goal files of goals `DONE` for more than a few days (from `control/goals/`);
- `done`/`cancelled` INBOX rows and old DECISIONS rows when a ledger grows past
  `ledger_archive_kb` in `control/hub-config.json` — into a dated file such as `archive/INBOX-<YYYY-MM>.md`;
- results and QA reports of finished goals, if `results/` becomes hard to scan;
- partial ingest files from `project/_ingest/` after a merge pass.

Rules: move with no clobber (`mv -n`); keep the original file name, prefixed with the date when needed;
never edit an archived file; ids found here still count as used (`tools/hub.py next-id` scans this folder).
