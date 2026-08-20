#!/usr/bin/env python3
"""Rules audit scanner for skill-curator.

Scans ~/.claude/rules/*.md (plus any extra directories passed in) for:
  - Duplicates: rule fragments with high similarity (SequenceMatcher >= 0.70)
  - Contradictions: opposing prescriptions on the same keyword (never X vs always X)
  - Stale: files unchanged for > 180 days without --enforced-- / --active-- marker

Safety: hardcoded whitelist of safety-critical rules is NEVER returned as a candidate.

Usage:
  ~/.local/bin/python3 rules_scan.py            # human-readable markdown
  ~/.local/bin/python3 rules_scan.py --json     # JSON output
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path

HOME = Path(os.path.expanduser("~"))
RULES_DIRS = [
    HOME / ".claude" / "rules",
    HOME / "workshop" / ".claude" / "rules",
]

# Hardcoded safety whitelist — these files (and the named coding-discipline section)
# never appear as audit candidates.
SAFETY_WHITELIST_FILES = {
    "bash-safety.md",
    "security.md",
    "skill-publishing-gate.md",
    "agents.md",
    "coding-discipline.md",  # §4.1 Hypothesis Discipline must be protected
}

STALE_DAYS = 180
DUP_THRESHOLD = 0.70
MIN_SEGMENT_CHARS = 80  # ignore tiny fragments

PROHIBIT_TOKENS = ["never", "禁止", "不要", "must not", "do not", "禁用"]
REQUIRE_TOKENS = ["always", "必須", "must", "required", "強制"]
ACTIVE_MARKERS = ["--enforced--", "--active--"]


def discover_rule_files() -> list[Path]:
    """Return all .md files under the configured rules dirs, skipping whitelist."""
    files: list[Path] = []
    for d in RULES_DIRS:
        if not d.exists():
            continue
        for p in sorted(d.glob("*.md")):
            if p.name in SAFETY_WHITELIST_FILES:
                continue
            files.append(p)
    return files


def split_segments(text: str, path: Path) -> list[tuple[int, str]]:
    """Split a rule file into (line_no, segment_text) pairs by H2 headings."""
    lines = text.splitlines()
    segments: list[tuple[int, str]] = []
    current_start = 0
    current_lines: list[str] = []
    for idx, line in enumerate(lines):
        if line.startswith("## "):
            if current_lines:
                seg = "\n".join(current_lines).strip()
                if len(seg) >= MIN_SEGMENT_CHARS:
                    segments.append((current_start + 1, seg))
            current_start = idx
            current_lines = [line]
        else:
            current_lines.append(line)
    if current_lines:
        seg = "\n".join(current_lines).strip()
        if len(seg) >= MIN_SEGMENT_CHARS:
            segments.append((current_start + 1, seg))
    return segments


def find_duplicates(files: list[Path]) -> list[dict]:
    """Cross-file pairwise segment similarity. Reports pairs >= DUP_THRESHOLD."""
    all_segs: list[tuple[Path, int, str]] = []
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line_no, seg in split_segments(text, f):
            all_segs.append((f, line_no, seg))

    dups: list[dict] = []
    seen_pairs: set[tuple] = set()
    for i in range(len(all_segs)):
        f_a, ln_a, s_a = all_segs[i]
        for j in range(i + 1, len(all_segs)):
            f_b, ln_b, s_b = all_segs[j]
            if f_a == f_b:
                continue  # only cross-file dupes
            ratio = SequenceMatcher(None, s_a, s_b).ratio()
            if ratio < DUP_THRESHOLD:
                continue
            key = tuple(sorted([(str(f_a), ln_a), (str(f_b), ln_b)]))
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
            head_a = s_a.splitlines()[0][:60]
            head_b = s_b.splitlines()[0][:60]
            dups.append(
                {
                    "file_a": str(f_a),
                    "line_a": ln_a,
                    "file_b": str(f_b),
                    "line_b": ln_b,
                    "similarity": round(ratio, 3),
                    "comment": f"Similar H2 segments: '{head_a}' vs '{head_b}'",
                }
            )
    return dups


def find_contradictions(files: list[Path]) -> list[dict]:
    """Heuristic: collide prohibit vs require tokens around the same keyword."""
    # Capture (file, line, keyword, polarity, snippet)
    bullets: list[tuple[Path, int, str, str, str]] = []
    keyword_re = re.compile(r"`([^`]{2,40})`|\*\*([^*]{2,40})\*\*")
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for idx, line in enumerate(text.splitlines(), start=1):
            low = line.lower()
            polarity: str | None = None
            for t in PROHIBIT_TOKENS:
                if t in low:
                    polarity = "prohibit"
                    break
            if polarity is None:
                for t in REQUIRE_TOKENS:
                    if t in low:
                        polarity = "require"
                        break
            if polarity is None:
                continue
            for m in keyword_re.finditer(line):
                kw = (m.group(1) or m.group(2) or "").strip().lower()
                if len(kw) < 3:
                    continue
                bullets.append((f, idx, kw, polarity, line.strip()[:120]))

    contradictions: list[dict] = []
    seen: set[tuple] = set()
    by_kw: dict[str, list] = {}
    for entry in bullets:
        by_kw.setdefault(entry[2], []).append(entry)
    for kw, entries in by_kw.items():
        prohibits = [e for e in entries if e[3] == "prohibit"]
        requires = [e for e in entries if e[3] == "require"]
        if not prohibits or not requires:
            continue
        for p in prohibits:
            for r in requires:
                if p[0] == r[0] and abs(p[1] - r[1]) < 3:
                    continue  # same paragraph: probably an exception clause
                key = (str(p[0]), p[1], str(r[0]), r[1], kw)
                if key in seen:
                    continue
                seen.add(key)
                contradictions.append(
                    {
                        "keyword": kw,
                        "prohibit": {
                            "file": str(p[0]),
                            "line": p[1],
                            "snippet": p[4],
                        },
                        "require": {
                            "file": str(r[0]),
                            "line": r[1],
                            "snippet": r[4],
                        },
                        "comment": f"Keyword `{kw}` flagged prohibit and require across files",
                    }
                )
    return contradictions


def git_last_modified(path: Path) -> date | None:
    """Return last commit date for path, or file mtime fallback."""
    try:
        res = subprocess.run(
            ["git", "-C", str(path.parent), "log", "-1", "--format=%cs", "--", path.name],
            capture_output=True,
            text=True,
            timeout=5,
        )
        out = res.stdout.strip()
        if out:
            return datetime.strptime(out, "%Y-%m-%d").date()
    except (subprocess.SubprocessError, ValueError, FileNotFoundError):
        pass
    try:
        return date.fromtimestamp(path.stat().st_mtime)
    except OSError:
        return None


def find_stale(files: list[Path]) -> list[dict]:
    """Files older than STALE_DAYS without an active marker."""
    today = date.today()
    cutoff = today - timedelta(days=STALE_DAYS)
    stale: list[dict] = []
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if any(marker in text for marker in ACTIVE_MARKERS):
            continue
        last_mod = git_last_modified(f)
        if last_mod is None or last_mod > cutoff:
            continue
        age = (today - last_mod).days
        stale.append(
            {
                "file": str(f),
                "last_modified": last_mod.isoformat(),
                "age_days": age,
                "comment": f"Untouched for {age} days; no --enforced-- / --active-- marker found",
            }
        )
    return stale


def render_markdown(result: dict) -> str:
    lines = ["## Rules Audit", ""]
    lines.append(
        f"_Scanned {result['scanned_files']} files (safety whitelist excluded: {', '.join(sorted(SAFETY_WHITELIST_FILES))})._"
    )
    lines.append("")

    lines.append("### Duplicates")
    if not result["duplicates"]:
        lines.append("- (none)")
    else:
        for d in result["duplicates"]:
            lines.append(
                f"- `{d['file_a']}:{d['line_a']}` ↔ `{d['file_b']}:{d['line_b']}` "
                f"(sim={d['similarity']}) — {d['comment']}"
            )
    lines.append("")

    lines.append("### Contradictions")
    if not result["contradictions"]:
        lines.append("- (none)")
    else:
        for c in result["contradictions"]:
            lines.append(
                f"- keyword `{c['keyword']}`: prohibit at "
                f"`{c['prohibit']['file']}:{c['prohibit']['line']}` vs require at "
                f"`{c['require']['file']}:{c['require']['line']}` — {c['comment']}"
            )
    lines.append("")

    lines.append(f"### Stale (>{STALE_DAYS} days)")
    if not result["stale"]:
        lines.append("- (none)")
    else:
        for s in result["stale"]:
            lines.append(
                f"- `{s['file']}` last modified {s['last_modified']} "
                f"({s['age_days']}d) — {s['comment']}"
            )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="emit JSON instead of markdown")
    args = ap.parse_args()

    files = discover_rule_files()
    result = {
        "scanned_files": len(files),
        "safety_whitelist": sorted(SAFETY_WHITELIST_FILES),
        "duplicates": find_duplicates(files),
        "contradictions": find_contradictions(files),
        "stale": find_stale(files),
    }

    if args.json:
        json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_markdown(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
