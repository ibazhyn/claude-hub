# Context manifest

> One row per file ingested from `context/`. Written by `hub-context-analyst`; read by
> `python tools/hub.py context-diff`, which compares the files on disk with these rows (by sha256) to find
> new, changed and removed files. Keep the table shape: path and sha256 in backticks, one row per file.
> Status is `ingested`, `skipped (format)` or `removed`.

| path | bytes | sha256 | ingested | status | summary |
|---|---|---|---|---|---|
