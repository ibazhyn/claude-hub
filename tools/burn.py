#!/usr/bin/env python3
"""Where this hub's tokens went. Usage: python tools/burn.py [DAYS] [--all]

Reads the local Claude Code transcripts of THIS hub (auto-located: <claude config>/projects/<slug>, where
the slug is the hub path with every non-alphanumeric character replaced by '-'), for the last DAYS days
(default 7). --all reads every local project. Counts main-session transcripts AND the subagent transcripts
Claude Code writes beside them (<session>/subagents/**), where workers and QA run. The context-size table
covers main sessions only - that is the context the orchestrator itself grows. A call is a unique
message id: a response is written as one line per content block, and those lines are counted once.

$ figures are API list-price equivalents from tools/model_prices.py - a proportion meter, not a bill.
Cache read is charged on EVERY call, so a token added at call N is paid again on every call after it:
session length, not model choice, dominates the total. Standard library only; Python 3.8+.
"""
import collections
import datetime
import glob
import json
import os
import re
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from model_prices import call_cost, resolve  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.join(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude"),
                    "projects")
SLUG = re.sub(r"[^A-Za-z0-9]", "-", HUB)


def locate():
    """The project folder of this hub; falls back to a case-insensitive match on the slug."""
    exact = os.path.join(ROOT, SLUG)
    if os.path.isdir(exact):
        return os.path.basename(exact)
    for d in glob.glob(os.path.join(ROOT, "*")):
        if os.path.basename(d).lower() == SLUG.lower():
            return os.path.basename(d)
    return None


days = 7
for a in sys.argv[1:]:
    if a.isdigit():
        days = int(a)
allp = "--all" in sys.argv
now = datetime.datetime.now(datetime.timezone.utc)
lo = (now - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
proj = "*" if allp else locate()
if proj is None:
    print("No transcripts found for this hub under %s (expected folder %s)." % (ROOT, SLUG))
    print("Open the hub in Claude Code at least once, or run with --all to read every local project.")
    sys.exit(0)


def fresh(f):
    try:
        mt = datetime.datetime.fromtimestamp(os.path.getmtime(f), datetime.timezone.utc)
    except OSError:
        return False
    return (now - mt).days <= days + 2


SEEN = set()   # message ids already counted, across every transcript read


def api_calls(f):
    """Yield (day, model, usage, content) once per real API call inside the window.

    Claude Code writes one line per content block of a response; the lines share message.id and repeat its
    usage. So a call is a unique message id, counted once, with the usage of its last line and the content
    blocks of all its lines. A line without an id is not a call."""
    calls = collections.OrderedDict()
    with open(f, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if '"usage"' not in line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            m = d.get("message") if isinstance(d, dict) else None
            u = m.get("usage") if isinstance(m, dict) else None
            if not isinstance(u, dict) or not u or d.get("type") != "assistant" or m.get("model") == "<synthetic>":
                continue  # <synthetic> = a locally written error turn: no API call, zero usage
            mid = m.get("id")
            if not isinstance(mid, str) or not mid or mid in SEEN:
                continue
            blocks = m.get("content") if isinstance(m.get("content"), list) else []
            if mid in calls:
                calls[mid]["usage"] = u
                calls[mid]["content"].extend(blocks)
            else:
                calls[mid] = {"ts": (d.get("timestamp") or "")[:10], "model": m.get("model"), "usage": u,
                              "content": list(blocks)}
    SEEN.update(calls)
    for c in calls.values():
        if c["ts"] and c["ts"] >= lo:
            yield c["ts"], c["model"], c["usage"], c["content"]


def new_row(f):
    return dict(proj=os.path.basename(os.path.dirname(f)), id=os.path.basename(f)[:8], calls=0, cost=0.0,
                out=0, maxctx=0, prefix=0, agents=0, day="", tools=collections.Counter(), subcalls=0,
                subcost=0.0)


sess = {}
byday, byband, bandcalls, bymodel, unpriced = (collections.Counter() for _ in range(5))
totals = {"main": 0.0, "sub": 0.0, "main_calls": 0, "sub_calls": 0}


def account(ts, model, c):
    key, known = resolve(model)
    bymodel[key if known else "%s*" % model] += c
    if not known:
        unpriced[model] += 1
    byday[ts] += c


for f in glob.glob(os.path.join(ROOT, proj, "*.jsonl")):
    if not fresh(f):
        continue
    f = os.path.normpath(f)
    r = new_row(f)
    for ts, model, u, cc in api_calls(f):
        c = call_cost(model, u)
        i = u.get("input_tokens", 0) or 0
        cw = u.get("cache_creation_input_tokens", 0) or 0
        ctx = i + cw + (u.get("cache_read_input_tokens", 0) or 0)
        band = ("<100k" if ctx < 1e5 else "100-200k" if ctx < 2e5 else "200-400k" if ctx < 4e5
                else "400-600k" if ctx < 6e5 else "600k+")
        r["calls"] += 1
        r["cost"] += c
        r["out"] += u.get("output_tokens", 0) or 0
        r["maxctx"] = max(r["maxctx"], ctx)
        r["prefix"] = r["prefix"] or (i + cw)
        r["day"] = r["day"] or ts
        byband[band] += c
        bandcalls[band] += 1
        account(ts, model, c)
        totals["main"] += c
        totals["main_calls"] += 1
        if isinstance(cc, list):
            for b in cc:
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    r["tools"][b.get("name")] += 1
                    if b.get("name") in ("Agent", "Task"):
                        r["agents"] += 1
    if r["calls"]:
        sess[f] = r

# <project>/<session id>/subagents/**/*.jsonl - each is charged to the session that spawned it.
for f in glob.glob(os.path.join(ROOT, proj, "*", "subagents", "**", "*.jsonl"), recursive=True):
    if not fresh(f):
        continue
    rel = os.path.relpath(f, ROOT).split(os.sep)
    parent = os.path.normpath(os.path.join(ROOT, rel[0], rel[1] + ".jsonl"))
    for ts, model, u, _ in api_calls(f):
        c = call_cost(model, u)
        r = sess.get(parent)
        if r is None:
            r = sess[parent] = new_row(parent)
        r["day"] = r["day"] or ts
        r["subcalls"] += 1
        r["subcost"] += c
        account(ts, model, c)
        totals["sub"] += c
        totals["sub_calls"] += 1

main_total, sub_total = totals["main"], totals["sub"]
total = main_total + sub_total
scope = "all projects" if allp else proj
print("=== %s, last %dd === $%s API-equivalent over %s calls" % (
    scope, days, format(round(total), ","), format(totals["main_calls"] + totals["sub_calls"], ",")))
print("    main sessions $%s / %s calls    subagents $%s / %s calls\n" % (
    format(round(main_total), ","), format(totals["main_calls"], ","), format(round(sub_total), ","),
    format(totals["sub_calls"], ",")))
print("by day:", "  ".join("%s $%s" % (k[5:], format(round(v), ",")) for k, v in sorted(byday.items())))
print("by model:", "  ".join("%s $%s" % (k, format(round(v), ",")) for k, v in bymodel.most_common()))
if unpriced:
    print("UNPRICED - priced as the newest model of its family; add a row to tools/model_prices.py:",
          ", ".join("%s x%d" % (k, v) for k, v in unpriced.most_common()))
print("\n--- main sessions: cost per call by context size at that call ---")
print("%-12s%8s%10s%9s%9s" % ("context", "calls", "$", "% main", "$/call"))
for b in ["<100k", "100-200k", "200-400k", "400-600k", "600k+"]:
    if bandcalls[b]:
        print("%-12s%8d%10.0f%9.1f%9.3f" % (b, bandcalls[b], byband[b], 100 * byband[b] / max(main_total, 1e-9),
                                          byband[b] / bandcalls[b]))
print("\n--- sessions, costliest first (main context + the subagents it spawned) ---")
print("%-11s%-10s%6s%7s%9s%10s%8s%10s%8s  top tools" % ("day", "id", "calls", "agents", "prefix k", "max ctx k",
                                                          "$ main", "sub calls", "$ sub"))
for r in sorted(sess.values(), key=lambda x: -(x["cost"] + x["subcost"]))[:15]:
    tt = ", ".join("%sx%d" % (k, v) for k, v in r["tools"].most_common(4))
    print("%-11s%-10s%6d%7d%9.0f%10.0f%8.0f%10d%8.0f  %s" % (r["day"], r["id"], r["calls"], r["agents"],
                                                            r["prefix"] / 1e3, r["maxctx"] / 1e3, r["cost"],
                                                            r["subcalls"], r["subcost"], tt))
over = sum(r["cost"] for r in sess.values() if r["maxctx"] > 2e5)
print("\nmain-session spend in sessions that grew past 200k context: $%s = %.0f%% of main-session spend"
      % (format(round(over), ","), 100 * over / max(main_total, 1e-9)))
