[English](README.md) | [繁體中文](README.zh.md)

# skill-curator

Analyze skill inventory for overlaps and redundancies using a 3-agent review panel.

## Description

Skill Curator runs a structured review of the installed skills, uses a 3-agent panel to evaluate redundancies and overlaps, and executes approved merges, splits, or deletions.

## Features

- Identifies overlapping and redundant skills across the inventory
- 3-agent panel discussion (explorer + reviewer + worker) for unbiased evaluation
- Recommends merge, split, deprecate, or keep decisions per skill
- User confirmation before any destructive operations
- Executes approved restructuring including SKILL.md updates
- Produces a curation report with rationale for each decision

## Usage

Invoke by asking Claude Code with trigger phrases such as:

- "organize my skills"
- "consolidate skills"
- "merge similar skills"
- "整理 skills"
- "skill 太多了"

## Related Skills

- [`skill-catalog`](https://github.com/joneshong-skills/skill-catalog)
- [`skill-graph`](https://github.com/joneshong-skills/skill-graph)
- [`skill-lifecycle`](https://github.com/joneshong-skills/skill-lifecycle)
- [`skill-optimizer`](https://github.com/joneshong-skills/skill-optimizer)

## Install

Copy the skill directory into your Claude Code skills folder:

```
cp -r skill-curator ~/.claude/skills/
```

Skills placed in `~/.claude/skills/` are auto-discovered by Claude Code. No additional registration is needed.
