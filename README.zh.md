[English](README.md) | [繁體中文](README.zh.md)

# skill-curator

Analyze skill inventory for overlaps and redundancies using a 3-agent review panel.

## 說明

Skill Curator runs a structured review of the installed skills, uses a 3-agent panel to evaluate redundancies and overlaps, and executes approved merges, splits, or deletions.

## 功能特色

- Identifies overlapping and redundant skills across the inventory
- 3-agent panel discussion (explorer + reviewer + worker) for unbiased evaluation
- Recommends merge, split, deprecate, or keep decisions per skill
- User confirmation before any destructive operations
- Executes approved restructuring including SKILL.md updates
- Produces a curation report with rationale for each decision

## 使用方式

透過以下觸發語句呼叫 Claude Code 來使用此技能：

- "organize my skills"
- "consolidate skills"
- "merge similar skills"
- "整理 skills"
- "skill 太多了"

## 相關技能

- [`skill-catalog`](https://github.com/joneshong-skills/skill-catalog)
- [`skill-graph`](https://github.com/joneshong-skills/skill-graph)
- [`skill-lifecycle`](https://github.com/joneshong-skills/skill-lifecycle)
- [`skill-optimizer`](https://github.com/joneshong-skills/skill-optimizer)

## 安裝

將技能目錄複製到 Claude Code 技能資料夾：

```
cp -r skill-curator ~/.claude/skills/
```

放置在 `~/.claude/skills/` 的技能會被 Claude Code 自動發現，無需額外註冊。
