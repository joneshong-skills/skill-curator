#!/usr/bin/env python3
"""Scan all skills and generate an overlap/redundancy report.

Usage:
    python3 analyze.py [--skills-dir ~/.claude/skills] [--json]

Output: Markdown report (default) or JSON with overlap clusters,
trigger phrase collisions, and tool profile similarities.
"""

import os
import re
import sys
import json
import argparse
from pathlib import Path
from collections import defaultdict
from itertools import combinations
from typing import Optional, Dict, List, Set


def parse_frontmatter(skill_path: Path) -> Optional[dict]:
    """Extract YAML frontmatter from SKILL.md (simple parser, no deps)."""
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return None

    text = skill_md.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return None

    fm = {}
    raw = m.group(1)
    # Handle multiline description with >- syntax
    current_key = None
    current_val_lines = []

    for line in raw.split("\n"):
        # New key
        kv = re.match(r"^(\w[\w-]*):\s*(.*)", line)
        if kv and not line.startswith("  "):
            if current_key:
                fm[current_key] = " ".join(current_val_lines).strip()
            current_key = kv.group(1)
            val = kv.group(2).strip()
            if val in (">-", ">", "|", "|-"):
                current_val_lines = []
            else:
                current_val_lines = [val]
        elif current_key and line.startswith("  "):
            current_val_lines.append(line.strip())

    if current_key:
        fm[current_key] = " ".join(current_val_lines).strip()

    # Parse body line count (after frontmatter)
    body = text[m.end():]
    fm["_body_lines"] = len(body.strip().split("\n")) if body.strip() else 0
    fm["_path"] = str(skill_path)

    return fm


def extract_triggers(description: str) -> List[str]:
    """Pull quoted trigger phrases from description."""
    return re.findall(r'"([^"]+)"', description)


def extract_keywords(description: str) -> Set[str]:
    """Extract meaningful words (>3 chars, lowercase) from description."""
    words = re.findall(r"[a-zA-Z\u4e00-\u9fff]{2,}", description.lower())
    stopwords = {
        # --- English stopwords ---
        # Articles & conjunctions
        "the", "an", "and", "or", "but",
        # Prepositions
        "in", "on", "at", "to", "for", "of", "with", "by", "from",
        "into", "about", "after", "before", "over",
        # Be / auxiliaries
        "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did",
        "will", "would", "could", "should", "may", "might", "can",
        # Pronouns & demonstratives
        "this", "that", "these", "those", "it", "its",
        "they", "them", "their",
        # Negation / logic
        "not", "no", "if", "then", "than", "so", "as",
        # Adverbs / quantifiers
        "also", "just", "only", "very", "more", "most",
        "some", "any", "all", "each", "every", "both",
        "few", "many", "much", "such",
        # Other common function words
        "other", "another", "same", "different", "new",
        "when", "how", "what", "which", "who", "where", "why",
        # Common verbs that don't carry domain meaning
        "use", "used", "using", "make", "like",
        # Common nouns in skill descriptions (too generic to differentiate)
        "user", "users", "skill", "skills", "tool", "tools",
        "file", "files",
        # Words frequently found in SKILL.md trigger-phrase boilerplate
        "asks", "mentions", "discusses", "including", "provides",
        # --- Chinese stopwords (繁體) ---
        "的", "是", "在", "了", "和", "與", "或", "也", "都",
        "不", "有", "這", "那", "就", "要", "會",
        "可以", "可", "能", "把", "讓", "被",
        "對", "從", "到", "做", "用", "使用", "需要",
        "一個", "這個", "那個",
        "如果", "當", "時", "進行", "以及", "等", "及",
    }
    return {w for w in words if w not in stopwords}


def extract_tools(fm: dict) -> Set[str]:
    """Extract tool list from frontmatter."""
    tools_str = fm.get("tools", "")
    if not tools_str:
        return set()
    return {t.strip() for t in tools_str.split(",") if t.strip()}


def jaccard(a: set, b: set) -> float:
    """Jaccard similarity between two sets."""
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


def compute_overlap(skills: Dict[str, dict]) -> List[dict]:
    """Compute pairwise overlap scores between all skills."""
    results = []
    names = sorted(skills.keys())

    for a, b in combinations(names, 2):
        fa, fb = skills[a], skills[b]

        desc_a = fa.get("description", "")
        desc_b = fb.get("description", "")

        kw_a = extract_keywords(desc_a)
        kw_b = extract_keywords(desc_b)
        kw_sim = jaccard(kw_a, kw_b)

        tools_a = extract_tools(fa)
        tools_b = extract_tools(fb)
        tool_sim = jaccard(tools_a, tools_b)

        trigs_a = set(t.lower() for t in extract_triggers(desc_a))
        trigs_b = set(t.lower() for t in extract_triggers(desc_b))
        trig_overlap = trigs_a & trigs_b

        # Weighted composite score
        composite = kw_sim * 0.5 + tool_sim * 0.2 + (0.3 if trig_overlap else 0)

        if composite > 0.15:  # threshold
            results.append({
                "pair": [a, b],
                "composite": round(composite, 3),
                "keyword_sim": round(kw_sim, 3),
                "tool_sim": round(tool_sim, 3),
                "trigger_overlap": sorted(trig_overlap),
                "shared_keywords": sorted(kw_a & kw_b)[:10],
            })

    results.sort(key=lambda x: x["composite"], reverse=True)
    return results


def find_clusters(overlaps: List[dict], threshold: float = 0.25) -> List[set]:
    """Group skills into clusters based on overlap scores (union-find)."""
    parent = {}

    def find(x):
        while parent.get(x, x) != x:
            parent[x] = parent.get(parent[x], parent[x])
            x = parent[x]
        return x

    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    for o in overlaps:
        if o["composite"] >= threshold:
            union(o["pair"][0], o["pair"][1])

    groups = defaultdict(set)
    all_skills = set()
    for o in overlaps:
        all_skills.update(o["pair"])
    for s in all_skills:
        groups[find(s)].add(s)

    return [c for c in groups.values() if len(c) > 1]


def generate_report(skills: dict, overlaps: list, clusters: list) -> str:
    """Generate markdown report."""
    lines = ["# Skill Curation Report", ""]
    lines.append(f"**Total skills scanned:** {len(skills)}")
    lines.append(f"**Overlap pairs found:** {len(overlaps)}")
    lines.append(f"**Clusters identified:** {len(clusters)}")
    lines.append("")

    # Clusters
    if clusters:
        lines.append("## Clusters (Potential Merge Candidates)")
        lines.append("")
        for i, cluster in enumerate(clusters, 1):
            members = sorted(cluster)
            lines.append(f"### Cluster {i}: {', '.join(members)}")
            lines.append("")
            # Show pairwise scores within cluster
            for o in overlaps:
                if o["pair"][0] in cluster and o["pair"][1] in cluster:
                    lines.append(
                        f"- **{o['pair'][0]}** ↔ **{o['pair'][1]}**: "
                        f"composite={o['composite']}, "
                        f"kw={o['keyword_sim']}, "
                        f"tools={o['tool_sim']}"
                    )
                    if o["trigger_overlap"]:
                        lines.append(
                            f"  - Shared triggers: {', '.join(o['trigger_overlap'])}"
                        )
                    if o["shared_keywords"]:
                        lines.append(
                            f"  - Shared keywords: {', '.join(o['shared_keywords'][:8])}"
                        )
            lines.append("")

    # Top overlaps outside clusters
    lines.append("## All Overlap Pairs (score > 0.15)")
    lines.append("")
    lines.append("| Skill A | Skill B | Composite | Keywords | Tools | Triggers |")
    lines.append("|---------|---------|-----------|----------|-------|----------|")
    for o in overlaps[:30]:
        trigs = len(o["trigger_overlap"])
        lines.append(
            f"| {o['pair'][0]} | {o['pair'][1]} | "
            f"{o['composite']} | {o['keyword_sim']} | "
            f"{o['tool_sim']} | {trigs} shared |"
        )
    lines.append("")

    # Inventory summary
    lines.append("## Skill Inventory")
    lines.append("")
    lines.append("| Skill | Version | Body Lines | Tools |")
    lines.append("|-------|---------|------------|-------|")
    for name in sorted(skills):
        fm = skills[name]
        tools = fm.get("tools", "-")
        version = fm.get("version", "-")
        body = fm.get("_body_lines", "?")
        lines.append(f"| {name} | {version} | {body} | {tools[:50]} |")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Analyze skill overlap")
    parser.add_argument(
        "--skills-dir",
        default=os.path.expanduser("~/.claude/skills"),
        help="Path to skills directory",
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.25,
        help="Cluster threshold (default 0.25)",
    )
    args = parser.parse_args()

    skills_dir = Path(args.skills_dir)
    if not skills_dir.exists():
        print(f"Error: {skills_dir} not found", file=sys.stderr)
        sys.exit(1)

    # Scan all skills
    skills = {}
    for d in sorted(skills_dir.iterdir()):
        if d.is_dir() and not d.name.startswith("."):
            fm = parse_frontmatter(d)
            if fm:
                skills[fm.get("name", d.name)] = fm

    overlaps = compute_overlap(skills)
    clusters = find_clusters(overlaps, threshold=args.threshold)

    if args.json:
        print(json.dumps({
            "total_skills": len(skills),
            "overlaps": overlaps,
            "clusters": [sorted(c) for c in clusters],
        }, indent=2))
    else:
        print(generate_report(skills, overlaps, clusters))


if __name__ == "__main__":
    main()
