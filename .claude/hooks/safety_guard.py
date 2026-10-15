#!/usr/bin/env python3
"""PreToolUse safety guard of this hub, for the Bash, PowerShell, Write, Edit and NotebookEdit tools.

It denies, however the command is quoted, chained or wrapped (bash -c, powershell -Command, cmd /c,
eval, subshells, command substitutions, heredocs fed to a shell):
  * destructive git: reset (except `reset [HEAD] -- <paths>`), clean (except dry runs), checkout of paths
    (anything but `checkout -b <name>`), restore of the working tree, stash other than list/show, rebase,
    commit --amend / -a, add -A / -u / . , forced or deleting pushes (--force, -f, --force-with-lease,
    --delete, --mirror, +refspec, :ref), any push that is not a plain top-level `git push ...` (an option
    between git and push: -C, -c, --git-dir, --no-pager ...; git behind env, command, exec, xargs, &, a
    nested shell or substitution; git as a path or git.exe - the confirmation rule matches only the plain
    form), branch -D / -M / -C / -f, filter-branch / filter-repo, update-ref, reflog expire / delete,
    gc --prune, prune, removal of a worktree that is neither under the hub's worktrees/ nor a temporary
    hub-wt-* under the system temp directory;
  * author overrides (--author, -c user.*, `git config user.*` writes, GIT_AUTHOR_* / GIT_COMMITTER_*)
    and hook bypasses (--no-verify, commit -n, core.hooksPath);
  * recursive deletion of a repository root, a .git directory, the home directory, a drive root, the hub
    or its ledgers, a registered repository, or the current directory;
  * commit messages it cannot read (-F, -C, -c, --fixup, --squash, --template, no -m, a bare variable),
    PowerShell here-string syntax in the Bash tool, hub ids in their compound shapes (G-..., W###-S###,
    S###-R## / -A##, IN-..., a W### named as a wave) / hub names / our units of work anywhere in the
    message (a lowercase determiner before a capitalised Wave/Session, or a numbered one), junk subjects,
    and subjects that miss control/hub-config.json -> commit.subject_regex when one is configured
    (until one is, a subject may not open with a bracketed prefix such as "[hub]");
  * Write/Edit/NotebookEdit inside any .git directory, or outside the write roots: the hub, the system temp
    directory, Claude's own project folder for this hub, and control/hub-config.json -> write_roots.

It is the floor of the contract, not the standard: CLAUDE.md and orchestration/04_GIT_SAFETY_AND_COMMITS.md
bind in full. Protocol: the tool call arrives as JSON on stdin. To deny, print hookSpecificOutput with
permissionDecision "deny" and exit 0; to allow, print nothing and exit 0. It fails OPEN on an unreadable
payload or an internal error, so a malformed payload can never brick a session; internal errors are noted
in safety_guard.err beside this file. If a command cannot be tokenized, a conservative pattern scan runs
instead. Standard library only; Python 3.8+.

Tests: python tools/guard_test.py
"""
import datetime
import json
import os
import re
import sys
import tempfile

HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
HUB = os.path.dirname(os.path.dirname(HOOK_DIR))
IS_WIN = os.name == "nt"
ERRLOG = os.path.join(HOOK_DIR, "safety_guard.err")
# The override exists for tools/guard_test.py; it is read from Claude Code's environment, which a command
# being checked cannot change.
CONFIG_PATH = os.environ.get("HUB_GUARD_CONFIG") or os.path.join(HUB, "control", "hub-config.json")

# Only shapes that are unmistakably ours. A bare S300, W123 or -R10 can be a product term (a model number, a
# flag), so a lone S###, W### or -R## is not refused; the contract still keeps our ids out of every message.
DEFAULT_BANNED = [
    (r"\bG-\d{8}-\d{3}\b", "a hub goal id (G-YYYYMMDD-NNN)"),
    (r"\bW\d{3}-S\d{3}\b", "a hub Session id (W###-S###)"),
    (r"\bS\d{3}-[RA]\d{2}\b", "a hub repair or continuation suffix (S###-R## / S###-A##)"),
    (r"(?i)\b(?:waves?\s*#?\s*W\d{3}|W\d{3}\s+waves?)\b", "a hub wave id (W### named as a wave)"),
    (r"\bIN-\d{8}-[A-Za-z0-9]+", "a hub INBOX id (IN-YYYYMMDD-...)"),
    (r"(?i)\bclaude[\s_-]*hub\b", "the hub's own name"),
    (r"(?i)\bhub-(?:orchestrator|session-worker|qa-reviewer|context-analyst|intake|setup|handoff)\b",
     "the name of a hub agent or skill"),
    (r"(?i)\bagent[\s_-]*hub\b", "the name of orchestration tooling"),
]
IDENTITY_KEYS = ("user.name", "user.email", "author.name", "author.email", "committer.name",
                 "committer.email")
HUB_STATE_DIRS = ("control", "project", "tasks", "results", "context", "archive", ".claude", "orchestration",
                  "tools")
POSIX_SHELLS = ("bash", "sh", "zsh", "dash", "ksh", "ash", "fish")
PS_SHELLS = ("powershell", "pwsh")

RULE = ("The subject names the product change: the repository's convention (project/CONVENTIONS.md), else "
        "'type(scope): outcome'. The Session id belongs in the result file, not in git. See "
        "orchestration/04_GIT_SAFETY_AND_COMMITS.md.")
AUTHOR_MSG = ("changing the commit author or committer is blocked (--author, -c user.*, git config user.*, "
              "GIT_AUTHOR_*/GIT_COMMITTER_*). Commits are authored by the identity recorded at setup; if "
              "`git config user.email` is wrong, stop and tell the user, who fixes it.")
HOOKS_MSG = "bypassing git hooks is blocked (--no-verify, commit -n, core.hooksPath). Fix what the hook reports."
PUSH_FORM_BASH = 'cd "<repo>" && git push <remote> <branch>'
PUSH_FORM_PS = 'Set-Location "<repo>" first, then git push <remote> <branch> as a command of its own'
PUSH_FORM_MSG = ("git push is blocked in this form (%s): the permission rules ask the user to confirm only a "
                 "plain git push run from inside the repository. Push only as: %s "
                 "(orchestration/04_GIT_SAFETY_AND_COMMITS.md, Pushing).")
MSGFILE_MSG = ("%s is blocked: give the commit message inline with -m (one -m per paragraph) so its subject "
               "can be checked. -m \"$(cat <<'EOF' ... EOF)\" is also readable.")
UNREADABLE_MSG = ("the commit message could not be read, so it could not be checked. Pass it inline with -m "
                  "'<subject>' -m '<body>', or -m \"$(cat <<'EOF' ... EOF)\".")
HERESTRING_MSG = ("-m @'...'@ is PowerShell here-string syntax and this is the Bash tool. Bash passes the @ "
                  "through literally, so git would record the subject \"@\" with your real subject on line two "
                  "- and amend is forbidden, so it would be permanent. From Bash use one quoted -m per "
                  "paragraph: git commit -m 'type(scope): outcome' -m 'body' -- <paths>. Then check it with "
                  "git log -1 --format=%s")


class Deny(Exception):
    pass


class ParseError(Exception):
    pass


class Word(str):
    """A shell word; `quoted` is True when any part of it came from a quoted string."""
    quoted = False


def deny(msg):
    raise Deny(msg)


def note(why):
    """A guard that fails must say so somewhere. Bounded to the last 50 lines."""
    try:
        old = []
        if os.path.exists(ERRLOG):
            with open(ERRLOG, encoding="utf-8", errors="replace") as fh:
                old = fh.readlines()[-49:]
        with open(ERRLOG, "w", encoding="utf-8") as fh:
            fh.writelines(old)
            fh.write("%s %s\n" % (datetime.datetime.now().isoformat(timespec="seconds"), why))
    except Exception:
        pass


# ----------------------------------------------------------------------------------------------- config

def load_config():
    try:
        with open(CONFIG_PATH, encoding="utf-8-sig") as fh:   # -sig: a file saved with a BOM still parses
            cfg = json.load(fh)
        return cfg if isinstance(cfg, dict) else {}
    except Exception:
        return {}


class Ctx(object):
    def __init__(self, cwd, cfg):
        self.cwds = [cwd]
        self.bodies = []
        roots = cfg.get("write_roots")
        self.write_roots = [os.path.expanduser(r) for r in (roots if isinstance(roots, list) else [])
                            if isinstance(r, str) and r.strip()]
        commit = cfg.get("commit") if isinstance(cfg.get("commit"), dict) else {}
        self.subject_regex = commit.get("subject_regex") or cfg.get("commit_subject_regex") or None
        # The built-in list is the floor: config entries are added to it, never replace it, so patterns that
        # a newer engine ships reach an installation whose control/hub-config.json predates them.
        self.banned = list(DEFAULT_BANNED)
        known = set(p for p, _ in self.banned)
        banned = commit.get("banned")
        for b in (banned if isinstance(banned, list) else []):
            if isinstance(b, dict) and b.get("pattern") and str(b["pattern"]) not in known:
                self.banned.append((str(b["pattern"]), str(b.get("why") or "a banned pattern")))
                known.add(str(b["pattern"]))


# ------------------------------------------------------------------------------------------------ paths

def home():
    return os.path.expanduser("~")


def msys(p):
    """Git Bash paths on Windows: /c/Projects/x -> C:\\Projects\\x, /tmp/x -> <temp>\\x."""
    if not IS_WIN or not p.startswith("/"):
        return p
    m = re.match(r"^/([A-Za-z])(/.*)?$", p)
    if m:
        return m.group(1).upper() + ":" + (m.group(2) or "/").replace("/", "\\")
    if p == "/tmp" or p.startswith("/tmp/"):
        return tempfile.gettempdir() + p[4:].replace("/", "\\")
    return p


def norm(p):
    try:
        return os.path.normcase(os.path.realpath(p))
    except Exception:
        return os.path.normcase(os.path.abspath(p))


def is_within(child, parent):
    """Normalized paths: child equals parent or lies below it."""
    if child == parent:
        return True
    return child.startswith(parent if parent.endswith(os.sep) else parent + os.sep)


def is_fs_root(p):
    drive, rest = os.path.splitdrive(p)
    return rest in ("", "/", "\\")


def temp_roots():
    roots = [tempfile.gettempdir(), os.environ.get("TMP"), os.environ.get("TEMP"), os.environ.get("TMPDIR")]
    if not IS_WIN:
        roots += ["/tmp", "/var/tmp"]
    return [norm(r) for r in roots if r]


def claude_base():
    return os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(home(), ".claude")


def claude_dirs():
    """Claude's own folders for this hub: the project folder (auto memory lives there) and plans."""
    slug = re.sub(r"[^A-Za-z0-9]", "-", HUB)
    return [norm(os.path.join(claude_base(), "projects", slug)), norm(os.path.join(claude_base(), "plans"))]


def expand(s):
    """Expand ~ and environment references; None when something stays unresolved."""
    s = s.strip()
    if not s:
        return None
    s = re.sub(r"(?i)^(?:microsoft\.powershell\.core\\)?filesystem::", "", s)
    if s == "~" or s.startswith("~/") or s.startswith("~\\"):
        s = home() + s[1:]

    def ps_env(m):
        v = os.environ.get(m.group(1))
        if v is None and m.group(1).upper() in ("USERPROFILE", "HOME"):
            v = home()
        return v if v is not None else "\x00"
    s = re.sub(r"(?i)\$env:([A-Za-z_][A-Za-z0-9_]*)", ps_env, s)
    s = re.sub(r"\$\{?HOME\}?(?![A-Za-z0-9_])", lambda m: home(), s)
    s = os.path.expandvars(s)
    if "\x00" in s or "$" in s or "`" in s:
        return None
    if IS_WIN and re.search(r"%[^%\\/]+%", s):
        return None
    return s


def cut_glob(s):
    """A wildcard target deletes inside its directory: judge the directory."""
    m = re.search(r"[*?\[]", s)
    if not m:
        return s
    head = s[:m.start()]
    k = max(head.rfind("/"), head.rfind("\\"))
    if k < 0:
        return "."
    if k == 0:
        return s[0]
    base = head[:k]
    if IS_WIN and re.match(r"^[A-Za-z]:$", base):
        return base + "\\"
    return base


def resolve_targets(t, ctx):
    s = expand(t)
    if s is None:
        return None
    s = msys(s)
    if IS_WIN and re.match(r"^[A-Za-z]:$", s):
        s += "\\"
    s = cut_glob(s)
    if os.path.isabs(s):
        return [norm(s)]
    return [norm(os.path.join(c, s)) for c in ctx.cwds]


def protected_reason(p, ctx):
    if is_fs_root(p):
        return "a drive or filesystem root"
    if is_within(norm(home()), p):
        return "the home directory or one of its parents"
    if is_within(norm(HUB), p):
        return "this hub or one of its parents"
    if any(p == r for r in temp_roots()):
        return "the system temp directory itself"
    cb = norm(claude_base())
    if is_within(cb, p) or is_within(p, cb):
        return "Claude's own configuration and memory folder"
    for d in HUB_STATE_DIRS:
        if is_within(p, norm(os.path.join(HUB, d))):
            return "the hub's own state (%s/) - archive instead of deleting" % d
    for r in ctx.write_roots:
        if is_within(norm(msys(r)), p):
            return "a registered repository or one of its parents"
    if ".git" in re.split(r"[\\/]", p):
        return "a .git directory"
    if os.path.exists(os.path.join(p, ".git")):
        return "a repository root (it contains .git)"
    for c in ctx.cwds:
        if is_within(c, p):
            return "the current directory or one of its parents"
    return None


def check_delete(targets, ctx, what):
    if not targets:
        deny("%s with no explicit target is blocked: piped or implicit input cannot be inspected. Name a "
             "literal path." % what)
    for t in targets:
        paths = resolve_targets(t, ctx)
        if paths is None:
            deny("%s of '%s' is blocked: the target holds a variable or substitution that cannot be resolved "
                 "here. Use a literal path." % (what, t))
        for p in paths:
            why = protected_reason(p, ctx)
            if why:
                deny("%s of '%s' is blocked: it is %s. That would destroy work nobody can recover. Delete only "
                     "specific build or scratch folders inside a repository, and remove a temporary worktree "
                     "with `git worktree remove`." % (what, t, why))


def is_temp_worktree(p):
    """Temporary = strictly below the hub's worktrees/ folder (QA's fail-first worktrees; it never holds a
    Session's work), or named hub-wt-* AND under a temp root. A Session's parallel worktree (wt-<SESSION-ID>)
    or any other worktree may hold uncommitted work, so the guard never removes it."""
    hub_wt = norm(os.path.join(HUB, "worktrees"))
    if p != hub_wt and is_within(p, hub_wt):
        return True
    named = os.path.basename(p.rstrip("\\/")).lower().startswith("hub-wt-")
    return named and any(is_within(p, r) and p != r for r in temp_roots())


# ------------------------------------------------------------------------------------------- tokenizers

ANSI_C = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", "'": "'", '"': '"', "a": "\a", "b": "\b",
          "e": "\x1b", "f": "\f", "v": "\v", "0": "\0"}
PS_ESC = {"n": "\n", "t": "\t", "r": "\r", "0": "\0", "a": "\a", "b": "\b", "f": "\f", "v": "\v",
          "e": "\x1b"}
SUB = "\x00S%d\x00"
HEREDOC_RE = re.compile(r"(?<!<)<<(?!<)(-?)[ \t]*(?:'([^'\n]+)'|\"([^\"\n]+)\"|\\?([A-Za-z_][A-Za-z0-9_]*))")


def extract_heredocs(text, bodies):
    """Replace each terminated heredoc with a placeholder word and keep its body aside.

    The body of `cat > file <<EOF` is data, not commands; the body of `bash <<EOF` is a script, and the
    body of `-m "$(cat <<'EOF' ...)"` is a commit message. Unterminated ones are left alone."""
    out = []
    pos = 0
    while True:
        m = HEREDOC_RE.search(text, pos)
        if not m:
            out.append(text[pos:])
            break
        delim = m.group(2) or m.group(3) or m.group(4)
        strip_tabs = m.group(1) == "-"
        nl = text.find("\n", m.end())
        if nl < 0:
            out.append(text[pos:])
            break
        i = nl + 1
        found = None
        while i <= len(text):
            j = text.find("\n", i)
            line = text[i:] if j < 0 else text[i:j]
            cmp = line.lstrip("\t") if strip_tabs else line
            if cmp.rstrip("\r") == delim:
                found = (i, len(text) if j < 0 else j + 1)
                break
            if j < 0:
                break
            i = j + 1
        if not found:
            out.append(text[pos:m.end()])
            pos = m.end()
            continue
        body = text[nl + 1:found[0]]
        if body.endswith("\n"):
            body = body[:-1]
        bodies.append(body.rstrip("\r"))
        out.append(text[pos:m.start()])
        out.append(" \x00H%d\x00 " % (len(bodies) - 1))
        out.append(text[m.end():nl + 1])
        pos = found[1]
    return "".join(out)


def read_balanced(text, i, dialect):
    """From just after an opening parenthesis: -> (inner text, index after the closing one)."""
    depth = 1
    start = i
    n = len(text)
    while i < n:
        c = text[i]
        if dialect == "bash" and c == "\\":
            i += 2
            continue
        if dialect == "ps" and c == "`":
            i += 2
            continue
        if c == "'":
            j = text.find("'", i + 1)
            if j < 0:
                raise ParseError("unterminated quote")
            i = j + 1
            continue
        if c == '"':
            i += 1
            while i < n and text[i] != '"':
                if text[i] in ("\\" if dialect == "bash" else "`"):
                    i += 2
                    continue
                if text[i] == "$" and i + 1 < n and text[i + 1] == "(":
                    _, i = read_balanced(text, i + 2, dialect)
                    continue
                i += 1
            if i >= n:
                raise ParseError("unterminated quote")
            i += 1
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return text[start:i], i + 1
        i += 1
    raise ParseError("unbalanced parenthesis")


class Splitter(object):
    """Collects words into simple commands."""

    def __init__(self):
        self.cmds = []
        self.words = []
        self.cur = []
        self.in_word = False
        self.quoted = False

    def add(self, s, quoted=False):
        self.cur.append(s)
        self.in_word = True
        self.quoted = self.quoted or quoted

    def end_word(self):
        if self.in_word:
            w = Word("".join(self.cur))
            w.quoted = self.quoted
            self.words.append(w)
        self.cur = []
        self.in_word = False
        self.quoted = False

    def end_cmd(self):
        self.end_word()
        if self.words:
            self.cmds.append(self.words)
        self.words = []


def split_bash(text, subs):
    sp = Splitter()
    n = len(text)
    i = 0
    while i < n:
        c = text[i]
        if c == "\\":
            if i + 1 < n and text[i + 1] == "\n":
                i += 2
                continue
            if i + 1 < n:
                sp.add(text[i + 1], True)
            i += 2
            continue
        if c == "'":
            j = text.find("'", i + 1)
            if j < 0:
                raise ParseError("unterminated single quote")
            sp.add(text[i + 1:j], True)
            i = j + 1
            continue
        if c == "$" and text.startswith("$'", i):
            j = i + 2
            buf = []
            while j < n and text[j] != "'":
                if text[j] == "\\" and j + 1 < n:
                    buf.append(ANSI_C.get(text[j + 1], "\\" + text[j + 1]))
                    j += 2
                    continue
                buf.append(text[j])
                j += 1
            if j >= n:
                raise ParseError("unterminated $'...'")
            sp.add("".join(buf), True)
            i = j + 1
            continue
        if c == '"':
            j = i + 1
            buf = []
            while j < n and text[j] != '"':
                ch = text[j]
                if ch == "\\" and j + 1 < n:
                    if text[j + 1] in '"\\$`':
                        buf.append(text[j + 1])
                        j += 2
                        continue
                    if text[j + 1] == "\n":
                        j += 2
                        continue
                if ch == "$" and text.startswith("$((", j):
                    inner, k = read_balanced(text, j + 2, "bash")
                    buf.append("$(" + inner + ")")
                    j = k
                    continue
                if ch == "$" and j + 1 < n and text[j + 1] == "(":
                    inner, k = read_balanced(text, j + 2, "bash")
                    subs.append(inner)
                    buf.append(SUB % (len(subs) - 1))
                    j = k
                    continue
                if ch == "`":
                    k = text.find("`", j + 1)
                    if k < 0:
                        raise ParseError("unterminated backtick")
                    subs.append(text[j + 1:k])
                    buf.append(SUB % (len(subs) - 1))
                    j = k + 1
                    continue
                buf.append(ch)
                j += 1
            if j >= n:
                raise ParseError("unterminated double quote")
            sp.add("".join(buf), True)
            i = j + 1
            continue
        if c == "$" and text.startswith("$((", i):
            inner, k = read_balanced(text, i + 2, "bash")
            sp.add("$(" + inner + ")")
            i = k
            continue
        if c == "$" and i + 1 < n and text[i + 1] == "(":
            inner, k = read_balanced(text, i + 2, "bash")
            subs.append(inner)
            sp.add(SUB % (len(subs) - 1))
            i = k
            continue
        if c == "`":
            k = text.find("`", i + 1)
            if k < 0:
                raise ParseError("unterminated backtick")
            subs.append(text[i + 1:k])
            sp.add(SUB % (len(subs) - 1))
            i = k + 1
            continue
        if c == "#" and not sp.in_word:
            k = text.find("\n", i)
            i = n if k < 0 else k
            continue
        if c in " \t\r":
            sp.end_word()
            i += 1
            continue
        if c in "\n;":
            sp.end_cmd()
            i += 1
            continue
        if c == "&":
            if sp.in_word and sp.cur and sp.cur[-1].endswith((">", "<")):
                sp.add(c)
                i += 1
                continue
            if text.startswith("&>", i):
                sp.end_word()
                sp.add("&>")
                sp.end_word()
                i += 2
                continue
            sp.end_cmd()
            i += 2 if text.startswith("&&", i) else 1
            continue
        if c == "|":
            sp.end_cmd()
            i += 2 if (text.startswith("||", i) or text.startswith("|&", i)) else 1
            continue
        if c in "<>" and i + 1 < n and text[i + 1] == "(":
            inner, k = read_balanced(text, i + 2, "bash")
            subs.append(inner)
            sp.add(SUB % (len(subs) - 1))
            i = k
            continue
        if c in "()":
            sp.end_cmd()
            i += 1
            continue
        if c in "{}" and not sp.in_word and (i + 1 >= n or text[i + 1] in " \t\r\n;"):
            sp.end_cmd()
            i += 1
            continue
        sp.add(c)
        i += 1
    sp.end_cmd()
    return sp.cmds


def ps_subexpressions(body, subs):
    out = []
    i = 0
    while i < len(body):
        if body.startswith("$(", i):
            inner, k = read_balanced(body, i + 2, "ps")
            subs.append(inner)
            out.append(SUB % (len(subs) - 1))
            i = k
            continue
        out.append(body[i])
        i += 1
    return "".join(out)


def split_ps(text, subs):
    sp = Splitter()
    n = len(text)
    i = 0
    while i < n:
        c = text[i]
        if c == "@" and i + 1 < n and text[i + 1] in "'\"" and not sp.in_word:
            q = text[i + 1]
            j = i + 2
            while j < n and text[j] in " \t":
                j += 1
            if j < n and text[j] in "\r\n":
                if text[j] == "\r" and j + 1 < n and text[j + 1] == "\n":
                    j += 1
                start = j + 1
                m = re.compile(r"\r?\n" + re.escape(q) + "@").search(text, j)
                if not m:
                    raise ParseError("unterminated here-string")
                body = text[start:m.start()] if m.start() >= start else ""
                if q == '"':
                    body = ps_subexpressions(body, subs)
                sp.add(body, True)
                i = m.end()
                continue
        if c == "'":
            j = i + 1
            buf = []
            while True:
                k = text.find("'", j)
                if k < 0:
                    raise ParseError("unterminated single quote")
                if k + 1 < n and text[k + 1] == "'":
                    buf.append(text[j:k] + "'")
                    j = k + 2
                    continue
                buf.append(text[j:k])
                break
            sp.add("".join(buf), True)
            i = k + 1
            continue
        if c == '"':
            j = i + 1
            buf = []
            while j < n:
                ch = text[j]
                if ch == "`" and j + 1 < n:
                    buf.append(PS_ESC.get(text[j + 1], text[j + 1]))
                    j += 2
                    continue
                if ch == '"':
                    if j + 1 < n and text[j + 1] == '"':
                        buf.append('"')
                        j += 2
                        continue
                    break
                if ch == "$" and j + 1 < n and text[j + 1] == "(":
                    inner, k = read_balanced(text, j + 2, "ps")
                    subs.append(inner)
                    buf.append(SUB % (len(subs) - 1))
                    j = k
                    continue
                buf.append(ch)
                j += 1
            if j >= n:
                raise ParseError("unterminated double quote")
            sp.add("".join(buf), True)
            i = j + 1
            continue
        if c == "`":
            if i + 1 < n and text[i + 1] in "\r\n":
                i += 2
                if i < n and text[i - 1] == "\r" and text[i] == "\n":
                    i += 1
                continue
            if i + 1 < n:
                sp.add(text[i + 1], True)
            i += 2
            continue
        if c == "<" and text.startswith("<#", i):
            k = text.find("#>", i + 2)
            i = n if k < 0 else k + 2
            continue
        if c == "#" and not sp.in_word:
            k = text.find("\n", i)
            i = n if k < 0 else k
            continue
        if c == "$" and i + 1 < n and text[i + 1] == "(":
            inner, k = read_balanced(text, i + 2, "ps")
            subs.append(inner)
            sp.add(SUB % (len(subs) - 1))
            i = k
            continue
        if c in " \t\r":
            sp.end_word()
            i += 1
            continue
        if c in "\n;":
            sp.end_cmd()
            i += 1
            continue
        if c == "|":
            sp.end_cmd()
            i += 2 if text.startswith("||", i) else 1
            continue
        if c == "&":
            if text.startswith("&&", i):
                sp.end_cmd()
                i += 2
                continue
            if sp.in_word:
                sp.add(c)
                i += 1
                continue
            sp.words.append(Word("&"))
            i += 1
            continue
        if c in "(){}":
            sp.end_cmd()
            i += 1
            continue
        sp.add(c)
        i += 1
    sp.end_cmd()
    return sp.cmds


def split_cmd(text):
    sp = Splitter()
    n = len(text)
    i = 0
    while i < n:
        c = text[i]
        if c == "^" and i + 1 < n:
            sp.add(text[i + 1], True)
            i += 2
            continue
        if c == '"':
            j = text.find('"', i + 1)
            j = n if j < 0 else j
            sp.add(text[i + 1:j], True)
            i = j + 1
            continue
        if c in " \t\r":
            sp.end_word()
            i += 1
            continue
        if c == "\n":
            sp.end_cmd()
            i += 1
            continue
        if c in "&|":
            sp.end_cmd()
            i += 2 if text.startswith(c * 2, i) else 1
            continue
        if c in "()":
            sp.end_cmd()
            i += 1
            continue
        sp.add(c)
        i += 1
    sp.end_cmd()
    return sp.cmds


# -------------------------------------------------------------------------------------------- analysis

AUTHOR_ENV = re.compile(r"(?i)\bGIT_(?:AUTHOR|COMMITTER)_(?:NAME|EMAIL)\b['\"]?\s*[=,]")
AUTHOR_ENV_PS = re.compile(r"(?i)\benv:GIT_(?:AUTHOR|COMMITTER)_(?:NAME|EMAIL)\b")
REDIR_OP = re.compile(r"^(?:\d+|&|\*)?(?:>>?|<<<|<|>&|<&|>\|)$")
REDIR_ATTACHED = re.compile(r"^(?:\d+|&|\*)?(?:>>?|<|>&|<&|>\|)\S+$")
ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\[[^\]]*\])?\+?=")
HEREDOC_REF = re.compile(r"\x00H(\d+)\x00")


def base_cmd(word):
    w = word.replace("\\", "/").rsplit("/", 1)[-1].lower()
    for ext in (".exe", ".cmd", ".bat", ".com"):
        if w.endswith(ext):
            return w[:-len(ext)]
    return w


def strip_redirections(words):
    out, herestrings = [], []
    i = 0
    while i < len(words):
        w = words[i]
        if not getattr(w, "quoted", False):
            if REDIR_OP.match(w):
                if w.endswith("<<<") and i + 1 < len(words):
                    herestrings.append(words[i + 1])
                i += 2
                continue
            if REDIR_ATTACHED.match(w):
                i += 1
                continue
        out.append(w)
        i += 1
    return out, herestrings


def skip_prefixes(words, i):
    while i < len(words):
        w = base_cmd(words[i])
        if w in ("sudo", "doas"):
            i += 1
            while i < len(words) and words[i].startswith("-"):
                i += 2 if words[i] in ("-u", "-g", "-h", "-p", "-C", "-D", "-U", "-r", "-t") else 1
            continue
        if w in ("command", "builtin", "exec", "nohup", "time", "&", ".", "call"):   # & and . : PowerShell
            i += 1
            while w not in ("&", ".") and i < len(words) and words[i].startswith("-"):
                i += 1
            continue
        if w == "nice":
            i += 1
            if i < len(words) and words[i] == "-n":
                i += 2
            elif i < len(words) and re.match(r"^-\d+$", words[i]):
                i += 1
            continue
        if w == "env":
            i += 1
            while i < len(words) and (words[i].startswith("-") or ASSIGN.match(words[i])):
                i += 2 if words[i] in ("-u", "-C", "-S") else 1
            continue
        if w == "xargs":
            i += 1
            while i < len(words) and words[i].startswith("-"):
                i += 2 if words[i] in ("-I", "-n", "-P", "-L", "-s", "-d", "-E", "-a") else 1
            continue
        if w == "timeout":
            i += 1
            while i < len(words) and words[i].startswith("-"):
                i += 2 if words[i] in ("-s", "-k") else 1
            i += 1
            continue
        break
    return i


def analyze(text, dialect, ctx, depth):
    if depth > 6:
        deny("the command nests shells or substitutions too deeply to inspect. Run simpler commands.")
    if dialect == "bash":
        text = extract_heredocs(text, ctx.bodies)
    if AUTHOR_ENV.search(text) or (dialect == "ps" and AUTHOR_ENV_PS.search(text)):
        deny(AUTHOR_MSG)
    subs = []
    if dialect == "bash":
        cmds = split_bash(text, subs)
    elif dialect == "ps":
        cmds = split_ps(text, subs)
    else:
        cmds = split_cmd(text)
    for words in cmds:
        analyze_simple(words, dialect, ctx, subs, depth)
    for inner in subs:
        analyze(inner, dialect, ctx, depth + 1)


def git_launch(raw, words, i, depth):
    """How git was reached, or None when it is the plain first word of a top-level command - the only form
    the push confirmation rule (`ask` in .claude/settings.json) matches."""
    if depth:
        return "git runs inside a nested shell, eval or command substitution"
    k = next((j for j, w in enumerate(raw) if w is words[i]), len(raw))
    if k:
        return "'%s' comes before git" % " ".join(raw[:k])
    quoted = getattr(words[i], "quoted", False)
    if words[i] != "git" or quoted:
        return "git is invoked as '%s'%s" % (words[i], ", quoted" if quoted else "")
    return None


def analyze_simple(words, dialect, ctx, subs, depth):
    herestrings = []
    raw = words
    if dialect in ("bash", "ps"):
        words, herestrings = strip_redirections(words)
    i = 0
    if dialect == "bash":
        while i < len(words) and ASSIGN.match(words[i]):
            i += 1
    i = skip_prefixes(words, i)
    if i >= len(words):
        return
    cmd = base_cmd(words[i])
    args = words[i + 1:]
    heredocs = [int(k) for a in args for k in HEREDOC_REF.findall(a)]

    if cmd in ("cd", "pushd", "chdir", "set-location", "sl", "push-location"):
        track_cd(args, ctx)
        return
    if cmd == "git":
        analyze_git(args, dialect, ctx, subs, git_launch(raw, words, i, depth))
        return
    if cmd in ("git-filter-repo", "git-filter-branch"):
        deny("rewriting history (%s) is blocked. History is never rewritten here." % cmd)
    if cmd in POSIX_SHELLS:
        j = 0
        while j < len(args):
            a = args[j]
            if a.startswith("-") and not a.startswith("--") and "c" in a[1:]:
                if j + 1 < len(args):
                    analyze(args[j + 1], "bash", ctx, depth + 1)
                break
            if a.startswith("-") or a.startswith("+"):
                j += 1
                continue
            break
        for k in heredocs:
            analyze(ctx.bodies[k], "bash", ctx, depth + 1)
        for h in herestrings:
            analyze(h, "bash", ctx, depth + 1)
        return
    if cmd in PS_SHELLS:
        for j, a in enumerate(args):
            al = a.lower()
            if al == "-ec" or (len(al) >= 2 and "-encodedcommand".startswith(al)):
                deny("an encoded PowerShell command cannot be inspected. Run the command in plain text.")
            if len(al) >= 2 and "-command".startswith(al):
                analyze(" ".join(args[j + 1:]), "ps", ctx, depth + 1)
                break
            if al in ("-file", "-f"):
                break
        for k in heredocs:
            analyze(ctx.bodies[k], "ps", ctx, depth + 1)
        for h in herestrings:
            analyze(h, "ps", ctx, depth + 1)
        return
    if cmd == "cmd":
        for j, a in enumerate(args):
            if a.lower() in ("/c", "/k", "/r", "//c", "//k"):
                analyze(" ".join(args[j + 1:]), "cmd", ctx, depth + 1)
                break
        return
    if cmd == "eval" and dialect == "bash":
        analyze(" ".join(args), "bash", ctx, depth + 1)
        return
    if cmd in ("invoke-expression", "iex") and dialect == "ps":
        analyze(" ".join(a for a in args if not a.lower().startswith("-c")), "ps", ctx, depth + 1)
        return
    if cmd == "wsl":
        j = 0
        while j < len(args) and args[j].startswith("-"):
            if args[j] in ("-e", "--exec", "--"):
                j += 1
                break
            j += 2 if args[j] in ("-d", "--distribution", "-u", "--user", "--cd") else 1
        analyze(" ".join(args[j:]), "bash", ctx, depth + 1)
        return
    if dialect == "bash" and cmd == "rm":
        rm_posix(args, ctx)
    elif dialect == "ps" and cmd in ("remove-item", "rm", "ri", "rmdir", "rd", "del", "erase"):
        rm_ps(args, ctx)
    elif dialect == "cmd" and cmd in ("rd", "rmdir", "del", "erase"):
        rm_cmd(args, ctx)


def track_cd(args, ctx):
    target = None
    for j, a in enumerate(args):
        if a.lower() in ("-path", "-literalpath", "-lp") and j + 1 < len(args):
            target = args[j + 1]
    if target is None:
        plain = [a for a in args if not a.startswith("-")]
        target = plain[0] if plain else "~"
    if target == "-":
        return
    s = expand(target)
    if s is None:
        return
    s = msys(s)
    if not os.path.isabs(s):
        s = os.path.join(ctx.cwds[-1], s)
    ctx.cwds.append(norm(s))


def rm_posix(args, ctx):
    recursive = False
    targets = []
    opts = True
    for a in args:
        if opts and a == "--":
            opts = False
            continue
        if opts and a.startswith("--"):
            recursive = recursive or a == "--recursive"
            continue
        if opts and a.startswith("-") and len(a) > 1:
            recursive = recursive or "r" in a[1:] or "R" in a[1:]
            continue
        targets.append(a)
    if recursive:
        check_delete(targets, ctx, "rm -r")


def rm_ps(args, ctx):
    recursive = False
    targets = []
    i = 0
    while i < len(args):
        a = args[i]
        al = a.lower()
        if al in ("/s", "/q", "/f"):
            recursive = recursive or al == "/s"
            i += 1
            continue
        if al.startswith("-") and len(al) > 1:
            name = al[1:].split(":", 1)[0]
            if name and "recurse".startswith(name):
                recursive = True
            elif (len(name) >= 2 and ("path".startswith(name) or "literalpath".startswith(name))) \
                    or name in ("lp", "pspath"):
                if ":" in a[1:]:
                    targets.append(a.split(":", 1)[1])
                elif i + 1 < len(args):
                    targets.append(args[i + 1])
                    i += 1
            elif name in ("include", "exclude", "filter", "credential", "stream"):
                i += 1
            i += 1
            continue
        targets.extend(p.strip() for p in a.split(",") if p.strip())
        i += 1
    if recursive:
        check_delete(targets, ctx, "Remove-Item -Recurse")


def rm_cmd(args, ctx):
    if any(a.lower() in ("/s", "//s") for a in args):
        check_delete([a for a in args if not a.startswith("/")], ctx, "a recursive rd/del")


# ----------------------------------------------------------------------------------------- git rules

def analyze_git(args, dialect, ctx, subs, launch=None):
    """`launch`: how git was reached when not as the plain first word of a top-level command (git_launch)."""
    i = 0
    cfgs = []
    cpath = None
    while i < len(args):
        a = args[i]
        if a == "-C":
            cpath = args[i + 1] if i + 1 < len(args) else None
            i += 2
            continue
        if a in ("-c", "--config-env"):
            if i + 1 < len(args):
                cfgs.append(args[i + 1])
            i += 2
            continue
        if a.startswith("--config-env="):
            cfgs.append(a.split("=", 1)[1])
            i += 1
            continue
        if a in ("--git-dir", "--work-tree", "--namespace", "--super-prefix", "--attr-source", "--list-cmds"):
            i += 2
            continue
        if a.startswith("-"):
            i += 1
            continue
        break
    for c in cfgs:
        key = c.split("=", 1)[0].strip().lower()
        if key in IDENTITY_KEYS:
            deny(AUTHOR_MSG)
        if key == "core.hookspath":
            deny(HOOKS_MSG)
    if i >= len(args):
        return
    sub = args[i].lower()
    rest = list(args[i + 1:])
    if "--no-verify" in rest:
        deny(HOOKS_MSG)
    base = ctx.cwds[-1]
    if cpath:
        s = expand(cpath)
        if s is not None:
            s = msys(s)
            base = norm(s if os.path.isabs(s) else os.path.join(base, s))
    rule = GIT_RULES.get(sub)
    if rule:
        rule(rest, dialect, ctx, subs, base)
    if sub == "push":
        # The `ask` rule in .claude/settings.json matches a command that starts `git push` and nothing else, so
        # any other spelling would push without the confirmation the contract requires.
        how = launch
        if not how and i:
            how = "'%s' comes between git and push" % " ".join(args[:i])
        quoted = getattr(args[i], "quoted", False)
        if not how and (args[i] != "push" or quoted):
            how = "push is written as '%s'%s" % (args[i], ", quoted" if quoted else "")
        if how:
            deny(PUSH_FORM_MSG % (how, PUSH_FORM_PS if dialect == "ps" else PUSH_FORM_BASH))


def short_flags(t):
    return t[1:] if t.startswith("-") and not t.startswith("--") and len(t) > 1 else ""


def g_reset(rest, dialect, ctx, subs, base):
    toks = [t for t in rest if t not in ("-q", "--quiet")]
    if "--" in toks:
        k = toks.index("--")
        before, after = toks[:k], toks[k + 1:]
        if after and (not before or (len(before) == 1 and before[0].upper() == "HEAD")):
            return
    if any(t in ("--hard", "--merge", "--keep") for t in toks):
        deny("git reset --hard/--merge/--keep is blocked: it discards uncommitted work, and the tree may hold "
             "the user's or a peer's changes. Nothing here is ever reset.")
    deny("git reset is blocked except `git reset [HEAD] -- <paths>`: moving the branch rewrites local history. "
         "To unstage a file use `git restore --staged <file>`.")


def g_clean(rest, dialect, ctx, subs, base):
    for t in rest:
        if t == "--dry-run" or "n" in short_flags(t):
            return
    deny("git clean is blocked (only a dry run -n is allowed): it deletes untracked files that may be the "
         "user's or a peer's work, with no way back.")


def g_checkout(rest, dialect, ctx, subs, base):
    toks = [t for t in rest if t not in ("-q", "--quiet")]
    if not toks:
        return
    if "-b" in toks:
        k = toks.index("-b")
        if k + 1 < len(toks) and not toks[k + 1].startswith("-"):
            others = toks[:k] + toks[k + 2:]
            opts = [t for t in others if t.startswith("-")]
            pos = [t for t in others if not t.startswith("-")]
            if all(o in ("--track", "--no-track", "-t") for o in opts) and len(pos) <= 1 \
                    and "." not in pos:
                return
    deny("git checkout is blocked except `git checkout -b <new-branch>`: `checkout <path>`, `checkout -- "
         "<path>` and `checkout .` silently overwrite uncommitted work. Switch branches with `git switch "
         "<branch>`, create one with `git switch -c <name>`, unstage with `git restore --staged <file>`.")


def g_switch(rest, dialect, ctx, subs, base):
    for t in rest:
        if t in ("--discard-changes", "--force", "-f", "--force-create", "-C", "--orphan") or \
                any(ch in short_flags(t) for ch in "fC"):
            deny("git switch %s is blocked: it discards or overwrites work. A plain `git switch <branch>` "
                 "refuses when local changes would be lost - let it." % t)


def g_restore(rest, dialect, ctx, subs, base):
    staged = worktree = False
    for t in rest:
        if t == "--":
            break
        if t == "--staged":
            staged = True
        elif t == "--worktree":
            worktree = True
        else:
            f = short_flags(t)
            staged = staged or "S" in f
            worktree = worktree or "W" in f
    if staged and not worktree:
        return
    deny("git restore of the working tree is blocked: it discards uncommitted changes. Only "
         "`git restore --staged <file>` (unstage) is allowed.")


def g_stash(rest, dialect, ctx, subs, base):
    if rest and rest[0].lower() in ("list", "show"):
        return
    deny("git stash is blocked (only `stash list` / `stash show`): stashing hides the user's or a peer's work "
         "in a shared tree, and pops lose it.")


def g_rebase(rest, dialect, ctx, subs, base):
    deny("git rebase is blocked: history is never rewritten here.")


def g_history(rest, dialect, ctx, subs, base):
    deny("rewriting refs or history (filter-branch, filter-repo, update-ref, prune) is blocked.")


def g_reflog(rest, dialect, ctx, subs, base):
    if rest and rest[0].lower() in ("expire", "delete"):
        deny("git reflog expire/delete is blocked: the reflog is the last way back to lost commits.")


def g_gc(rest, dialect, ctx, subs, base):
    if any(t == "--prune" or t.startswith("--prune=") for t in rest):
        deny("git gc --prune is blocked: it deletes unreachable commits that may still be needed. Plain "
             "`git gc` is fine.")


def g_push(rest, dialect, ctx, subs, base):
    for t in rest:
        if t == "--":
            continue
        name = t.split("=", 1)[0].lower()
        if name in ("--force", "--force-with-lease", "--force-if-includes", "--delete", "--mirror", "--prune"):
            deny("git push %s is blocked: it overwrites or deletes remote history." % t)
        if t.startswith("--"):
            continue
        f = short_flags(t)
        if f:
            if "f" in f or "d" in f:
                deny("git push %s is blocked: it overwrites or deletes remote history." % t)
            continue
        if t.startswith("+") or (t.startswith(":") and len(t) > 1):
            deny("git push with the refspec '%s' is blocked: a leading + forces, a leading : deletes." % t)


def g_branch(rest, dialect, ctx, subs, base):
    force = False
    for t in rest:
        if t == "--":
            break
        if t.startswith("--"):
            force = force or t.split("=", 1)[0] == "--force"
            continue
        f = short_flags(t)
        if any(ch in f for ch in "DMC"):
            deny("git branch %s is blocked: it deletes or overwrites a branch. `git branch -d <merged>` is "
                 "allowed." % t)
        force = force or "f" in f
    if force:
        deny("git branch --force is blocked: it resets or deletes a branch regardless of its commits.")


def g_add(rest, dialect, ctx, subs, base):
    after_dd = False
    for t in rest:
        if t == "--":
            after_dd = True
            continue
        if not after_dd:
            if t in ("-A", "--all", "-u", "--update", "--no-ignore-removal") or \
                    any(ch in short_flags(t) for ch in "Au"):
                deny("git add %s is blocked: it stages everything, including the user's or a peer's changes. "
                     "Stage explicit task-owned paths: git add -- <paths>." % t)
            if t.startswith("-"):
                continue
        if t in (".", "./", ".\\", ":/", ":/*", ":(top)", "*", ":"):
            deny("git add %s is blocked: it stages everything, including the user's or a peer's changes. "
                 "Stage explicit task-owned paths: git add -- <paths>." % t)


def g_config(rest, dialect, ctx, subs, base):
    """Reading user.* or core.hooksPath is fine; writing them is an author override or a hook bypass."""
    keys = [k for k, t in enumerate(rest) if t.lower() in IDENTITY_KEYS + ("core.hookspath",)]
    if not keys:
        return
    why = HOOKS_MSG if rest[keys[0]].lower() == "core.hookspath" else AUTHOR_MSG
    writes = ("--unset", "--unset-all", "--replace-all", "--add", "--rename-section", "--remove-section",
              "--edit", "-e")
    if any(t in writes for t in rest) or (rest and rest[0].lower() in ("set", "unset", "rename-section",
                                                                         "remove-section", "edit")):
        deny(why)
    if any(not t.startswith("-") for t in rest[keys[0] + 1:]):
        deny(why)


def g_worktree(rest, dialect, ctx, subs, base):
    if not rest or rest[0].lower() != "remove":
        return
    targets = [t for t in rest[1:] if not t.startswith("-")]
    if not targets:
        deny("git worktree remove without a path cannot be checked.")
    for t in targets:
        s = expand(t)
        if s is None:
            deny("git worktree remove '%s': the path cannot be resolved here. Use a literal path." % t)
        s = msys(s)
        if dialect == "ps" and os.sep == "/":
            s = s.replace("\\", "/")  # PowerShell on macOS/Linux accepts \ as a path separator
        p = norm(s if os.path.isabs(s) else os.path.join(base, s))
        if not is_temp_worktree(p):
            deny("git worktree remove '%s' is blocked: only temporary worktrees (inside the hub's worktrees/ "
                 "folder, or named hub-wt-* under the system temp directory) may be removed. Other worktrees "
                 "may hold someone's work - leave them and name them in the result." % t)


def g_commit(rest, dialect, ctx, subs, base):
    msgs = []
    i = 0
    while i < len(rest):
        t = rest[i]
        if t == "--":
            break
        if t.startswith("--"):
            name, eq, val = t.partition("=")
            if name == "--message":
                if eq:
                    msgs.append(val)
                elif i + 1 < len(rest):
                    msgs.append(rest[i + 1])
                    i += 1
            elif name in ("--file", "--reuse-message", "--reedit-message", "--fixup", "--squash", "--template"):
                deny(MSGFILE_MSG % name)
            elif name == "--amend":
                deny("git commit --amend is blocked: a landed commit is never rewritten. A follow-up problem is "
                     "a second commit.")
            elif name == "--all":
                deny("git commit --all is blocked: it sweeps every modified tracked file, including the user's "
                     "or a peer's. Commit explicit paths: git commit -m '<subject>' -- <paths>.")
            elif name in ("--author", "--reset-author"):
                deny(AUTHOR_MSG)
            i += 1
            continue
        if t.startswith("-") and len(t) > 1:
            j = 1
            while j < len(t):
                ch = t[j]
                if ch in "mFCct":
                    if j + 1 < len(t):
                        val = t[j + 1:]
                    elif i + 1 < len(rest):
                        val = rest[i + 1]
                        i += 1
                    else:
                        val = None
                    if ch == "m":
                        if val is not None:
                            msgs.append(val)
                    else:
                        deny(MSGFILE_MSG % ("-" + ch))
                    break
                if ch in "Su":
                    break
                if ch == "a":
                    deny("git commit -a is blocked: it sweeps every modified tracked file, including the "
                         "user's or a peer's. Commit explicit paths: git commit -m '<subject>' -- <paths>.")
                if ch == "n":
                    deny(HOOKS_MSG)
                j += 1
            i += 1
            continue
        i += 1
    check_messages(msgs, dialect, ctx, subs)


HEREDOC_CAT = re.compile(r"^\s*cat\s+(?:-\s+)?\x00H(\d+)\x00\s*$")
SUB_REF = re.compile(r"\x00S(\d+)\x00")
BARE_VAR = re.compile(r"^\s*\$\{?[A-Za-z_][A-Za-z0-9_:]*\}?\s*$")
# Our units of work: numbered ("Wave 29"; in the subject also "session #3"), or pointed at as ours - a
# lowercase determiner before the capitalised noun our bookkeeping uses ("both Sessions", "this Wave").
# Product wording stays legal: "a session cookie", "every session", "each Session field", "Session tokens",
# and Title Case subjects such as "Fix Login For Every Session". Quantifiers (each, every, all, same,
# another, other) are product wording far more often than bookkeeping, so they are not in the list.
UNIT_NUM_ANY = re.compile(r"\b(?:Waves?|Sessions?)\s*#?\d+\b")
UNIT_NUM_SUBJECT = re.compile(r"(?i)\b(?:waves?|sessions?)\s*#?\d+\b")
UNIT_OURS = re.compile(r"\b(?:this|that|our|both|previous|next|last|earlier|later|first|second|third)\s+"
                       r"(?:Waves?|Sessions?)(?:'s)?\b")


def resolve_message(m, subs, ctx):
    def repl(mm):
        h = HEREDOC_CAT.match(subs[int(mm.group(1))])
        if h:
            return ctx.bodies[int(h.group(1))]
        raise Deny(UNREADABLE_MSG)
    return SUB_REF.sub(repl, m)


def check_messages(msgs, dialect, ctx, subs):
    if not msgs:
        deny(UNREADABLE_MSG)
    texts = []
    for m in msgs:
        if dialect == "bash" and m.startswith("@"):
            deny(HERESTRING_MSG)
        if BARE_VAR.match(m):
            deny(UNREADABLE_MSG)
        texts.append(resolve_message(m, subs, ctx))
    subject = ""
    for line in texts[0].splitlines():
        if line.strip():
            subject = line.strip()
            break
    full = "\n".join(texts)
    # Junk, not shape: an empty subject, one starting with @ or a quote (a mangled here-string), or fewer than
    # four letters or digits in any script ("wip", "."; "v1.2.0" passes). Shape is checked only against a
    # configured subject_regex.
    if not subject or subject[0] in "@'\"`" or len(re.findall(r"[^\W_]", subject)) < 4:
        deny("the commit subject %r is not a subject. %s" % (subject, RULE))
    for pattern, why in ctx.banned:
        try:
            hit = re.search(pattern, full)
        except re.error:
            continue
        if hit:
            deny("the commit message contains %s ('%s'). That is the hub's internal bookkeeping, and everyone "
                 "who reads the history reads it. %s" % (why, hit.group(0), RULE))
    if UNIT_NUM_SUBJECT.search(subject) or UNIT_NUM_ANY.search(full) or UNIT_OURS.search(full):
        deny("the commit message names one of the hub's units of work (a wave or a Session). Say what changed "
             "in the product instead. %s" % RULE)
    if ctx.subject_regex:
        try:
            ok = re.search(ctx.subject_regex, subject) is not None
        except re.error:
            ok = True
        if not ok:
            deny("the commit subject %r does not match this hub's commit convention %r (control/hub-config.json "
                 "-> commit.subject_regex, from project/CONVENTIONS.md). %s" % (subject, ctx.subject_regex, RULE))
    elif subject.startswith("["):
        # No convention is configured yet: a bracketed prefix is neither the conventional form nor an observed
        # house style, and it is how internal bookkeeping ("[hub] ...") reaches a history.
        deny("the commit subject %r opens with a bracketed prefix, and no repository convention that uses one "
             "is configured. %s" % (subject, RULE))


GIT_RULES = {
    "reset": g_reset, "clean": g_clean, "checkout": g_checkout, "switch": g_switch, "restore": g_restore,
    "stash": g_stash, "rebase": g_rebase, "filter-branch": g_history, "filter-repo": g_history,
    "update-ref": g_history, "prune": g_history, "reflog": g_reflog, "gc": g_gc, "push": g_push,
    "branch": g_branch, "add": g_add, "config": g_config, "worktree": g_worktree, "commit": g_commit,
}

FALLBACK = [
    (r"(?i)\bgit\b[^\n;|&]*\breset\b", "git reset"),
    (r"(?i)\bgit\b[^\n;|&]*\bclean\b", "git clean"),
    (r"(?i)\bgit\b[^\n;|&]*\b(?:rebase|filter-branch|filter-repo|update-ref|stash)\b", "a history rewrite or stash"),
    (r"(?i)\bgit\b[^\n;|&]*\bpush\b[^\n;|&]*(?:--force|--delete|--mirror|\s-[A-Za-z]*[fd]\b|\s\+)",
     "a forced or deleting push"),
    (r"(?i)\bgit\b[^\n;|&]*\bcommit\b", "a git commit whose message cannot be checked"),
    (r"(?i)\bgit\b[^\n;|&]*\bcheckout\b", "git checkout"),
    (r"(?i)--no-verify", "--no-verify"),
    (r"(?i)\brm\s+-[A-Za-z]*[rR]", "a recursive rm"),
    (r"(?i)\bremove-item\b[^\n;|&]*\s-r", "a recursive Remove-Item"),
    (r"(?i)\b(?:rd|rmdir|del)\b[^\n;|&]*\s/s\b", "a recursive delete"),
]


def fallback(cmd):
    for rx, what in FALLBACK:
        if re.search(rx, cmd):
            deny("the command could not be parsed reliably, and it appears to contain %s. Rewrite it as simple "
                 "commands with balanced quotes." % what)


# ---------------------------------------------------------------------------------------------- checks

def check_write(path, ctx):
    p = msys(os.path.expanduser(path.strip()))
    if not os.path.isabs(p):
        p = os.path.join(ctx.cwds[0], p)
    pn = norm(p)
    if ".git" in re.split(r"[\\/]", pn):
        deny("writing inside a .git directory (%s) is blocked: git's internals change only through git "
             "commands." % path)
    roots = [norm(HUB)] + temp_roots() + claude_dirs() + [norm(msys(r)) for r in ctx.write_roots]
    if any(is_within(pn, r) for r in roots):
        return
    deny("writing outside the hub's write roots is blocked: %s. Allowed: this hub, the registered repositories "
         "(control/hub-config.json -> write_roots, filled by hub-setup) and the system temp directory. To work "
         "in another repository, register it first: 'add repository <name>, path <path>'." % path)


def check_shell(cmd, dialect, ctx):
    try:
        analyze(cmd, dialect, ctx, 0)
    except ParseError:
        fallback(cmd)


def main():
    data = sys.stdin.buffer.read() if hasattr(sys.stdin, "buffer") else sys.stdin.read().encode("utf-8")
    if not data or not data.strip():
        return
    try:
        ev = json.loads(data.decode("utf-8-sig", "replace"))
    except Exception:
        return
    if not isinstance(ev, dict):
        return
    tool = str(ev.get("tool_name") or "")
    ti = ev.get("tool_input")
    if not isinstance(ti, dict):
        return
    cwd = ev.get("cwd") if isinstance(ev.get("cwd"), str) and ev.get("cwd").strip() else os.getcwd()
    ctx = Ctx(norm(msys(cwd)), load_config())
    try:
        if tool in ("Write", "Edit", "NotebookEdit", "MultiEdit"):
            path = ti.get("file_path") or ti.get("notebook_path")
            if isinstance(path, str) and path.strip():
                check_write(path, ctx)
        elif tool in ("Bash", "PowerShell"):
            cmd = ti.get("command")
            if isinstance(cmd, str) and cmd.strip():
                check_shell(cmd, "bash" if tool == "Bash" else "ps", ctx)
    except Deny as d:
        out = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                      "permissionDecisionReason": "hub safety guard: " + str(d)}}
        sys.stdout.write(json.dumps(out))
        sys.stdout.flush()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # fail open, but leave a trace
        note("unhandled %s: %s" % (type(e).__name__, e))
    sys.exit(0)
