#!/usr/bin/env python3
"""Hub console - one call instead of a dozen file reads. Standard library only; Python 3.8+.

  python tools/hub.py status [--brief]
        configuration, repositories (path exists? branch), context drift, task queues and running work,
        tree locks with age, QA worktrees left in worktrees/ (qa-*), LIVE goals with owner and areas, open
        INBOX rows, handoff prompt age (a SETUP follow-up with a leftover <placeholder> or a json block that
        does not parse is reported BROKEN), ledger sizes. --brief: five lines (a sixth when QA worktrees are
        left over) and the recommended next action.
  python tools/hub.py next-id goal                          G-YYYYMMDD-NNN (today)
  python tools/hub.py next-id wave                          W###
  python tools/hub.py next-id session --wave W003           W003-S###  (without --wave: the most recent
                                                            wave with open Sessions; none -> an error)
  python tools/hub.py next-id repair --session W003-S002    W003-S002-R01, -R02, ...
  python tools/hub.py next-id continuation --session W003-S002   W003-S002-A02, -A03, ...
  python tools/hub.py next-id inbox --slug cart-total       IN-YYYYMMDD-CARTTOTAL
        Ids are scanned from tasks/, results/, control/goals/, the control ledgers, control/ids.log and
        archive/, never reused, and every allocation is appended to control/ids.log so two sessions never
        receive the same id before either has written a file. --peek shows the id without allocating it.
  python tools/hub.py context-diff [--json]
        new / changed / removed files in context/ versus project/CONTEXT_MANIFEST.md (sha256).
"""
import argparse
import datetime
import glob
import hashlib
import json
import os
import re
import subprocess
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATES = ("queued", "running", "done", "partial", "failed", "blocked", "superseded")
CONTEXT_README_MARKER = "<!-- hub:context-readme -->"
INBOX_STATUSES = ("unrouted", "held", "session", "routed", "done", "cancelled")
TEXT_FORMATS = (".md", ".markdown", ".txt")


def P(*parts):
    return os.path.join(HUB, *parts)


def read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def strip_noise(md):
    """Drop HTML comments and fenced code blocks: examples inside them are not records."""
    md = re.sub(r"<!--.*?-->", "", md, flags=re.S)
    return re.sub(r"(?ms)^\s*```.*?^\s*```[^\n]*$", "", md)


def front_matter(text):
    m = re.match(r"^﻿?---\s*\n(.*?)\n---\s*(\n|$)", text, re.S)
    out = {}
    if m:
        for line in m.group(1).splitlines():
            if ":" in line and not line.startswith((" ", "\t", "#")):
                k, v = line.split(":", 1)
                out[k.strip()] = v.strip()
    return out


def config():
    try:
        with open(P("control", "hub-config.json"), encoding="utf-8-sig") as fh:
            c = json.load(fh)
        return c if isinstance(c, dict) else {}
    except Exception:
        return {}


def age(ts):
    s = max(0, int(ts))
    if s < 3600:
        return "%dm" % (s // 60)
    if s < 86400:
        return "%dh" % (s // 3600)
    return "%dd" % (s // 86400)


def since(path):
    try:
        return age(datetime.datetime.now().timestamp() - os.path.getmtime(path))
    except OSError:
        return "?"


def epoch(iso):
    """ISO 8601 -> seconds since the epoch. A trailing Z is UTC and an explicit offset (+03:00, +0300) is
    honoured; a time without either is local time. Python 3.8's fromisoformat knows neither Z nor +0300, and
    takes a fraction of 3 or 6 digits only (PowerShell's Get-Date -Format o writes 7)."""
    s = iso.strip().strip("'\"")
    s = re.sub(r"[Zz]$", "+00:00", s)
    s = re.sub(r"([T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?[+-]\d{2})(\d{2})$", r"\1:\2", s)
    s = re.sub(r"(:\d{2})\.(\d+)", lambda m: m.group(1) + "." + (m.group(2) + "00000")[:6], s)
    return datetime.datetime.fromisoformat(s).timestamp()


def git(repo, *args):
    try:
        r = subprocess.run(["git", "-C", repo] + list(args), capture_output=True, timeout=15)
        return r.stdout.decode("utf-8", "replace").strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def table_rows(md):
    rows = []
    for line in strip_noise(md).splitlines():
        s = line.strip()
        if s.startswith("|") and not re.match(r"^\|[\s|:-]*\|$", s):
            rows.append([c.strip() for c in s.strip("|").split("|")])
    return rows


# ------------------------------------------------------------------------------------------------ state

def profile():
    return front_matter(read(P("project", "PROJECT_PROFILE.md")))


def repositories():
    text = strip_noise(read(P("project", "REPOSITORIES.md")))
    repos = []
    cur = None
    for line in text.splitlines():
        h = re.match(r"^##\s+`?([^`\s]+)`?\s*$", line)
        if h:
            cur = {"key": h.group(1)}
            repos.append(cur)
            continue
        f = re.match(r"^\s*-\s*([A-Za-z_]+)\s*:\s*(.*?)\s*$", line)
        if cur is not None and f and f.group(1) not in cur:
            cur[f.group(1)] = f.group(2)
    return [r for r in repos if r.get("path")]


def context_files():
    root = P("context")
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        for name in sorted(filenames):
            if name.startswith(".") or name.startswith("~$"):
                continue
            full = os.path.join(dirpath, name)
            rel = "context/" + os.path.relpath(full, root).replace(os.sep, "/")
            if rel == "context/README.md" and CONTEXT_README_MARKER in read(full)[:400]:
                continue
            h = hashlib.sha256()
            try:
                with open(full, "rb") as fh:
                    for chunk in iter(lambda: fh.read(1 << 20), b""):
                        h.update(chunk)
                size = os.path.getsize(full)
            except OSError:
                continue
            ext = os.path.splitext(name)[1].lower()
            fmt = "text" if ext in TEXT_FORMATS else ("pdf" if ext == ".pdf" else "other")
            files.append({"path": rel, "bytes": size, "sha256": h.hexdigest(), "format": fmt})
    return files


def cell(c):
    """A table cell without surrounding spaces and backticks - inner spaces are kept (file names have them)."""
    return c.strip().strip("`").strip()


def manifest():
    rows = {}
    for cells in table_rows(read(P("project", "CONTEXT_MANIFEST.md"))):
        clean = [cell(c) for c in cells]
        path = next((c for c in clean if c.startswith("context/")), None)
        if not path:
            continue
        sha = next((c.lower() for c in clean if re.match(r"^[0-9a-fA-F]{64}$", c)), "")
        status = next((c.split(" ")[0] for c in clean if c.split(" ")[0] in ("ingested", "skipped", "removed")),
                      "ingested")
        rows[path] = {"sha256": sha, "status": status}
    return rows


def drift():
    files = context_files()
    rows = manifest()
    new, changed, unchanged = [], [], 0
    for f in files:
        r = rows.get(f["path"])
        if r is None or r["status"] == "removed":
            new.append(f)
        elif r["sha256"] != f["sha256"]:
            changed.append(f)
        else:
            unchanged += 1
    on_disk = set(f["path"] for f in files)
    removed = [{"path": p} for p, r in sorted(rows.items()) if r["status"] != "removed" and p not in on_disk]
    return {"files": files, "new": new, "changed": changed, "removed": removed, "unchanged": unchanged,
            "manifest_rows": len(rows)}


def queues():
    counts, running = {}, []
    for st in STATES:
        names = sorted(os.path.basename(f) for f in glob.glob(P("tasks", st, "*.md")))
        counts[st] = len(names)
        if st == "running":
            running = names
    return counts, running


def locks():
    out = []
    for f in sorted(glob.glob(P("control", "locks", "TREE_LOCK-*.md"))):
        fm = front_matter(read(f))
        holder = fm.get("holder", "")
        if holder and holder.lower() not in ("none", "null", "-"):
            started = fm.get("started_at", "")
            try:
                a = age(datetime.datetime.now().timestamp() - epoch(started))
            except Exception:
                a = since(f)
            out.append({"repo": fm.get("repo") or os.path.basename(f)[10:-3], "holder": holder,
                        "goal": fm.get("goal", ""), "age": a})
    return out


def qa_leftovers():
    """What QA's fail-first step left in worktrees/: qa-<SESSION-ID> worktrees and their qa-* output files. The
    reviewer removes its own at the end, even on failure (orchestration/06_QA_AND_REPAIR.md)."""
    out = []
    for f in sorted(glob.glob(P("worktrees", "qa-*"))):
        repo = ""
        if os.path.isdir(f):   # a worktree's .git is a file: "gitdir: <repo>/.git/worktrees/<name>"
            m = re.match(r"gitdir:\s*(.+?)[\\/]+\.git[\\/]+worktrees[\\/]", read(os.path.join(f, ".git")).strip())
            repo = m.group(1) if m else "?"
        out.append({"name": os.path.basename(f), "dir": os.path.isdir(f), "repo": repo, "age": since(f)})
    return out


def goals():
    rows = []
    for cells in table_rows(read(P("control", "OPEN_GOALS.md"))):
        if not cells or not re.search(r"G-\d{8}-\d{3}", cells[0]):
            continue
        status = next((c.strip("`* ").upper() for c in cells if c.strip("`* ").upper() in ("LIVE", "PAUSED", "DONE")),
                      "?")
        cols = cells + [""] * 8
        rows.append({"goal": re.search(r"G-\d{8}-\d{3}", cells[0]).group(0), "title": cols[1],
                     "owner": cols[2], "areas": cols[3], "status": status, "last": cols[6]})
    files = len(glob.glob(P("control", "goals", "current-goal-*.md")))
    return rows, files


def inbox():
    """INBOX rows; the status is read from the `status` column only (the user's words may contain anything)."""
    rows = []
    col = None
    for cells in table_rows(read(P("control", "INBOX.md"))):
        low = [cell(c).lower() for c in cells]
        if col is None and "status" in low and "id" in low:
            col = low.index("status")
            continue
        m = re.search(r"IN-(\d{8})-[A-Za-z0-9-]+", cells[0] if cells else "")
        if not m:
            continue
        raw = cell(cells[col]) if col is not None and col < len(cells) else ""
        word = re.split(r"[\s`-]", raw.lower(), maxsplit=1)[0] if raw else ""
        st = word if word in INBOX_STATUSES else "unclassified"
        rows.append({"id": m.group(0), "date": m.group(1), "status": st})
    return rows


def handoff():
    """Sections are fenced <!-- NAME-BEGIN --> ... <!-- NAME-END -->; SETUP is the follow-up hub-setup leaves."""
    path = P("control", "NEXT-SESSION-PROMPT.md")
    text = read(path)
    sections = re.findall(r"(?m)^[ \t]*<!--\s*([A-Za-z0-9_-]+)-BEGIN\s*-->[ \t\r]*$", text)
    return {"empty": not sections, "sections": sections, "setup": "SETUP" in sections, "age": since(path),
            "setup_problems": setup_problems(text)}


def setup_problems(text):
    """What would make the SETUP follow-up mislead the next session: a placeholder left in it, or a ```json
    block that json.loads rejects. Setup writes the section once and must see none (05, Step 8)."""
    m = re.search(r"(?ms)^[ \t]*<!--\s*SETUP-BEGIN\s*-->(.*?)^[ \t]*<!--\s*SETUP-END\s*-->", text)
    if not m:
        return []
    body = m.group(1)
    out = []
    for n, block in enumerate(re.findall(r"(?ms)^[ \t]*```json[ \t]*\r?\n(.*?)^[ \t]*```", body), 1):
        try:
            json.loads(block)
        except ValueError as e:
            out.append("json block %d does not parse (%s)" % (n, e))
    holders = sorted(set(re.findall(r"<(?!!--)[^<>\n]{1,80}>", body)))
    if holders:
        out.append("placeholder(s) " + ", ".join(holders[:4]))
    return out


def ledger_sizes():
    limit = config().get("ledger_archive_kb") or 150
    out = []
    for name in ("INBOX.md", "DECISIONS.md", "OPEN_GOALS.md"):
        try:
            kb = os.path.getsize(P("control", name)) / 1024.0
        except OSError:
            continue
        out.append((name, kb, kb > limit))
    return out, limit


# ----------------------------------------------------------------------------------------------- status

def cmd_status(a):
    prof = profile()
    status = prof.get("status", "NOT_CONFIGURED") or "NOT_CONFIGURED"
    configured = status.upper() == "CONFIGURED"
    d = drift()
    repos = repositories()
    counts, running = queues()
    lk = locks()
    wt = qa_leftovers()
    grows, gfiles = goals()
    live = [g for g in grows if g["status"] == "LIVE"]
    paused = [g for g in grows if g["status"] == "PAUSED"]
    ib = inbox()
    open_ib = sorted((r for r in ib if r["status"] not in ("done", "cancelled")), key=lambda r: r["id"])
    ho = handoff()
    cfg = config()
    dcount = len(d["new"]) + len(d["changed"]) + len(d["removed"])

    if a.brief:
        if configured:
            print("profile: CONFIGURED (%s) | language %s | python %s" % (
                prof.get("configured_at", "?"), prof.get("language", "?"),
                " ".join(cfg.get("python_command") or []) or "?"))
        else:
            print("profile: %s -> run hub-setup before anything else" % status)
        if d["files"]:
            drift_txt = ("drift: %d new, %d changed, %d removed -> re-sync (hub-setup)" % (
                len(d["new"]), len(d["changed"]), len(d["removed"]))) if dcount else "no drift"
            print("context/: %d file(s): %s | %s" % (len(d["files"]), ", ".join(f["path"][8:] for f in d["files"][:6])
                                                     + (" ..." if len(d["files"]) > 6 else ""), drift_txt))
        else:
            print("context/: no project files yet (context/README.md is the hub's guide, not ingested)"
                  + ("" if not d["removed"] else " | drift: %d removed -> re-sync" % len(d["removed"])))
        if repos:
            missing = [r["key"] for r in repos if not os.path.isdir(os.path.expanduser(r["path"]))]
            print("repositories: %d (%s); missing paths: %s" % (len(repos), ", ".join(r["key"] for r in repos),
                                                                ", ".join(missing) or "none"))
        else:
            print("repositories: none registered")
        print("work: running %d%s | queued %d | LIVE goals %d%s | inbox open %d%s | locks held %d"
              % (counts["running"], (" (" + ", ".join(n[:-3] for n in running[:4]) + ")") if running else "",
                 counts["queued"], len(live),
                 (" (" + "; ".join("%s owner %s" % (g["goal"], g["owner"] or "?") for g in live[:3]) + ")") if live else "",
                 len(open_ib), (" (oldest %s)" % open_ib[0]["id"]) if open_ib else "", len(lk)))
        if wt:
            print("worktrees: %d QA leftover(s) in worktrees/ (%s) -> remove unless that QA is still running "
                  "(orchestration/06_QA_AND_REPAIR.md)" % (len(wt), ", ".join(w["name"] for w in wt[:4])
                                                            + (" ..." if len(wt) > 4 else "")))
        if ho["setup"]:
            print("handoff: SETUP FOLLOW-UP PENDING in control/NEXT-SESSION-PROMPT.md -> do it right after this "
                  "message's INBOX rows, without waiting (orchestration/05_SETUP_PROTOCOL.md, Next session)"
                  + ("" if not ho["setup_problems"] else
                     " | SETUP SECTION BROKEN: %s -> rewrite it from the real state" % "; ".join(ho["setup_problems"])))
        else:
            print("handoff: " + ("none pending" if ho["empty"] else
                                 "%s in NEXT-SESSION-PROMPT.md, updated %s ago -> offer to resume"
                                 % (", ".join(ho["sections"]), ho["age"])))
        return

    print("== hub ==  %s" % HUB)
    print("  profile: %s%s" % (status, (" at " + prof.get("configured_at", "?")) if configured else
                               "  -> run hub-setup (orchestration/05_SETUP_PROTOCOL.md)"))
    print("  language: %s | git identity: %s | python: %s" % (prof.get("language", "null"),
                                                              prof.get("git_identity", "null"),
                                                              " ".join(cfg.get("python_command") or []) or "null"))
    print("== repositories ==")
    if not repos:
        print("  none registered")
    for r in repos:
        path = os.path.expanduser(r["path"])
        exists = os.path.isdir(path)
        branch = git(path, "rev-parse", "--abbrev-ref", "HEAD") if exists else ""
        print("  %-16s %s  [%s]%s" % (r["key"], r["path"], "ok" if exists else "MISSING",
                                      ("  branch " + branch) if branch else ""))
    print("== context/ ==")
    if not d["files"]:
        print("  no project files yet (context/README.md is the hub's guide and is not ingested)")
    for f in d["files"]:
        print("  %-40s %8.1f KB  %s" % (f["path"], f["bytes"] / 1024.0, f["format"]))
    print("  manifest rows: %d | drift: %d new, %d changed, %d removed%s" % (
        d["manifest_rows"], len(d["new"]), len(d["changed"]), len(d["removed"]),
        "  -> re-sync (hub-setup)" if dcount else ""))
    print("== tasks ==")
    print("  " + " | ".join("%s %d" % (st, counts[st]) for st in STATES))
    for n in running:
        print("  running: %s (%s)" % (n, since(P("tasks", "running", n))))
    print("== locks ==")
    if not lk:
        print("  none held")
    for l in lk:
        print("  %s held by %s (goal %s) for %s" % (l["repo"], l["holder"], l["goal"] or "?", l["age"]))
    print("== worktrees ==  (QA's temporary worktrees; each reviewer removes its own, even on failure)")
    if not wt:
        print("  none left over")
    for w in wt:
        print("  %s  %s, %s old" % ("worktrees/" + w["name"], ("worktree of " + w["repo"]) if w["dir"] else "file",
                                    w["age"]))
    if wt:
        print("  ^ LEFT OVER unless that QA is still running: git -C \"<repo>\" worktree remove --force "
              "\"<hub>/worktrees/qa-<SESSION-ID>\", then delete its qa-<SESSION-ID>-*.txt files")
    print("== goals ==  (%d goal files in control/goals/)" % gfiles)
    if not grows:
        print("  none registered")
    for g in live:
        print("  LIVE    %s  owner %s  areas %s  last %s" % (g["goal"], g["owner"] or "?", g["areas"] or "?",
                                                          g["last"] or "?"))
    for g in paused:
        print("  PAUSED  %s  %s" % (g["goal"], g["title"]))
    done = len(grows) - len(live) - len(paused)
    if done:
        print("  done or unclassified: %d" % done)
    print("== inbox ==")
    tally = {}
    for r in ib:
        tally[r["status"]] = tally.get(r["status"], 0) + 1
    print("  " + (" | ".join("%s %d" % (k, v) for k, v in sorted(tally.items())) if tally else "empty"))
    if open_ib:
        print("  open: %d, oldest %s" % (len(open_ib), open_ib[0]["id"]))
    if tally.get("unrouted"):
        print("  ^ unrouted rows must not survive the intake turn")
    print("== handoff ==\n  NEXT-SESSION-PROMPT.md: %s (modified %s ago)%s" % (
        "empty" if ho["empty"] else "sections " + ", ".join(ho["sections"]), ho["age"],
        "\n  ^ SETUP follow-up pending: do it right after this message's INBOX rows "
        "(orchestration/05_SETUP_PROTOCOL.md, Next session)"
        if ho["setup"] else ""))
    if ho["setup_problems"]:
        print("  ^ SETUP SECTION BROKEN: %s -> rewrite it from the real state" % "; ".join(ho["setup_problems"]))
    sizes, limit = ledger_sizes()
    print("== ledgers ==  (archive threshold %s KB)" % limit)
    print("  " + " | ".join("%s %.1f KB%s" % (n, kb, " -> ARCHIVE done rows" if big else "") for n, kb, big in sizes))


# ---------------------------------------------------------------------------------------------- next-id

def id_corpus():
    """Every place an id may already be written: file names and contents. READMEs are documentation
    (their examples are not ids in use) and are skipped."""
    chunks = []
    paths = []
    for pattern in (("tasks", "**", "*"), ("results", "**", "*"), ("control", "goals", "**", "*"),
                    ("archive", "**", "*")):
        paths += glob.glob(P(*pattern), recursive=True)
    paths += [P("control", n) for n in ("INBOX.md", "OPEN_GOALS.md", "NEXT-SESSION-PROMPT.md", "DECISIONS.md",
                                         "ids.log")]
    paths += glob.glob(P("control", "locks", "*.md"))
    for p in paths:
        if os.path.basename(p) in ("README.md", ".keep"):
            continue
        if os.path.isfile(p):
            chunks.append(os.path.basename(p))
            if os.path.getsize(p) < 8 * 1024 * 1024:
                chunks.append(read(p))
    return "\n".join(chunks)


CYRILLIC = dict(zip("абвгдеёжзийклмнопрстуфхцчшщъыьэюяіїєґў",
                    ["A", "B", "V", "G", "D", "E", "E", "ZH", "Z", "I", "Y", "K", "L", "M", "N", "O", "P", "R", "S",
                     "T", "U", "F", "KH", "TS", "CH", "SH", "SHCH", "", "Y", "", "E", "YU", "YA", "I", "YI", "YE",
                     "G", "U"]))


def slugify(text):
    """INBOX slug: A-Z0-9 only, max 24 characters. Cyrillic is transliterated; other scripts fall back to a
    short hash, so a slug in any language still yields a stable id."""
    out = "".join(CYRILLIC.get(ch, ch) for ch in text.lower()).upper()
    slug = re.sub(r"[^A-Z0-9]", "", out)[:24]
    if not slug and text.strip():
        slug = "X" + hashlib.sha1(text.strip().encode("utf-8")).hexdigest()[:8].upper()
    return slug


def highest(pattern, corpus):
    nums = [int(x) for x in re.findall(pattern, corpus)]
    return max(nums) if nums else 0


def open_wave():
    """The most recent wave that still has open Sessions (an MD in tasks/queued/ or tasks/running/), or None."""
    waves = [int(m.group(1)) for st in ("queued", "running") for f in glob.glob(P("tasks", st, "*.md"))
             for m in [re.match(r"W(\d{3})-S\d{3}", os.path.basename(f), re.I)] if m]
    return ("W%03d" % max(waves)) if waves else None


def cmd_next_id(a):
    today = datetime.date.today().strftime("%Y%m%d")
    corpus = id_corpus()
    kind = a.kind
    if kind == "goal":
        new = "G-%s-%03d" % (today, highest(r"\bG-" + today + r"-(\d{3})\b", corpus) + 1)
    elif kind == "wave":
        new = "W%03d" % (highest(r"(?<![A-Za-z0-9])W(\d{3})(?![0-9])", corpus) + 1)
    elif kind == "session":
        if a.wave is None:
            w = open_wave()
            if not w:
                sys.exit("next-id session: no wave has open Sessions (tasks/queued/, tasks/running/) - pass "
                         "--wave W### (a new wave comes from: next-id wave)")
            sys.stderr.write("next-id session: no --wave given; using %s, the most recent wave with open "
                             "Sessions\n" % w)
        elif not re.match(r"^W?\d{1,3}$", a.wave, re.I):
            sys.exit("next-id session: --wave takes a wave id such as W003 (a new wave comes from: next-id wave)")
        else:
            w = "W%03d" % int(re.sub(r"\D", "", a.wave))
        new = "%s-S%03d" % (w, highest(r"\b" + w + r"-S(\d{3})(?![0-9])", corpus) + 1)
    elif kind in ("repair", "continuation"):
        if not a.session or not re.match(r"^W\d{3}-S\d{3}(-R\d{2})?$", a.session, re.I):
            sys.exit("next-id %s needs --session W###-S### (a continuation may also name a repair, W###-S###-R##)"
                     % kind)
        s = a.session.upper()
        if kind == "repair":
            s = s[:9]  # repairs are always numbered on the original Session: -R01, -R02, ...
            new = "%s-R%02d" % (s, highest(r"\b" + s + r"-R(\d{2})(?![0-9])", corpus) + 1)
        else:
            new = "%s-A%02d" % (s, max(1, highest(r"\b" + re.escape(s) + r"-A(\d{2})(?![0-9])", corpus)) + 1)
    else:  # inbox
        slug = slugify(a.slug or "")
        if not slug:
            sys.exit("next-id inbox needs --slug <word>, e.g. --slug cart-total")
        base = "IN-%s-%s" % (today, slug)
        new, n = base, 1
        while re.search(re.escape(new) + r"(?![A-Z0-9-])", corpus):
            n += 1
            new = "%s-%d" % (base, n)
    if not a.peek:
        with open(P("control", "ids.log"), "a", encoding="utf-8") as fh:
            fh.write("%s %s\n" % (datetime.datetime.now().isoformat(timespec="seconds"), new))
    print(new)


# ----------------------------------------------------------------------------------------- context-diff

def cmd_context_diff(a):
    d = drift()
    if a.json:
        keys = ("new", "changed", "removed", "unchanged", "manifest_rows", "files")
        print(json.dumps(dict((k, d[k]) for k in keys), indent=2))
        return
    total = sum(f["bytes"] for f in d["files"])
    print("context/: %d file(s), %.1f KB | manifest rows: %d" % (len(d["files"]), total / 1024.0, d["manifest_rows"]))
    for label in ("new", "changed"):
        for f in d[label]:
            print("  %-8s %-40s %8.1f KB  sha256 %s  (%s)" % (label, f["path"], f["bytes"] / 1024.0,
                                                           f["sha256"][:16], f["format"]))
    for f in d["removed"]:
        print("  removed  %s" % f["path"])
    print("  unchanged: %d" % d["unchanged"])
    if not (d["new"] or d["changed"] or d["removed"]):
        print("  no drift")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd")
    s = sub.add_parser("status")
    s.add_argument("--brief", action="store_true")
    s.set_defaults(fn=cmd_status)
    n = sub.add_parser("next-id")
    n.add_argument("kind", choices=("goal", "wave", "session", "repair", "continuation", "inbox"))
    n.add_argument("--wave")
    n.add_argument("--session")
    n.add_argument("--slug")
    n.add_argument("--peek", action="store_true", help="show the id without recording the allocation")
    n.set_defaults(fn=cmd_next_id)
    c = sub.add_parser("context-diff")
    c.add_argument("--json", action="store_true")
    c.set_defaults(fn=cmd_context_diff)
    a = p.parse_args()
    if not getattr(a, "fn", None):
        p.print_help()
        return 2
    a.fn(a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
