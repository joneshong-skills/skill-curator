---
name: skill-curator
description: >-
  This skill should be used when the user asks to "organize my skills",
  "consolidate skills", "merge similar skills", "clean up skills",
  "整理 skills", "收斂 skills", "skill 太多了", "哪些 skill 可以合併",
  mentions skill redundancy, or discusses reviewing, reorganizing,
  merging, or splitting their skill inventory.
version: 0.2.0
tools: Read, Glob, Grep, Bash, Edit, Write, Task
---

# Skill Curator

Analyze the skill inventory for overlaps and redundancies, use a 3-agent panel discussion
to reach consensus on recommendations, then execute approved restructuring.

## Guiding Philosophy

**Goldilocks granularity**: A skill = one coherent capability domain.
Not a single command (too small), not an entire discipline (too large).

Principles:
- **Flexibility** — No rigid rules; context determines the right boundary
- **Adaptability** — Skills evolve; what was two skills yesterday may be one today
- **Stay current** — Prune dead skills, merge converging ones, split outgrown ones

## Workflow

### Step 1: Scan

Run the overlap analysis to get clusters:

```bash
python3 ~/.claude/skills/skill-curator/scripts/analyze.py
```

Options: `--json` for machine-readable output, `--threshold 0.3` to adjust sensitivity.

### Step 2: Panel Discussion (3-Agent Consensus)

For each non-trivial cluster identified in Step 1, launch **3 parallel agents** using the
Task tool. Each agent reads the actual SKILL.md files of the cluster members and argues
from a different perspective.

#### Agent Roles

| Role | Bias | Focus |
|------|------|-------|
| **Consolidator** | Pro-merge | Finds redundancy, shared workflows, trigger collisions. Argues for fewer, broader skills. |
| **Preservationist** | Pro-keep | Finds distinctions in intent, audience, freedom level. Argues for specialized skills. |
| **Synthesizer** | Neutral | Weighs both sides, considers user experience and practical trade-offs. Produces the final recommendation. |

#### Prompt Templates

For each cluster, construct prompts like the following. The `{cluster_skills}` placeholder
is the list of skill names; `{skill_paths}` are the SKILL.md file paths to read.

**Consolidator prompt:**
```
You are the Consolidator in a skill curation panel. Your bias is toward MERGING skills
to reduce redundancy.

Cluster under review: {cluster_skills}

Read these SKILL.md files: {skill_paths}

For each pair, evaluate:
1. Trigger phrase overlap — would a user say the same thing for both?
2. Workflow overlap — what % of steps are shared?
3. Domain object — do they operate on the same thing?
4. Merge feasibility — would the combined SKILL.md stay under 500 lines?

Output a structured verdict for each pair:
- Pair: A ↔ B
- Merge score (0-10): [score]
- Key argument for merging: [1-2 sentences]
- Proposed merged name: [name]
- Risk of merging: [1 sentence]

Be specific. Cite actual content from the SKILL.md files you read.
```

**Preservationist prompt:**
```
You are the Preservationist in a skill curation panel. Your bias is toward KEEPING
skills separate to preserve specificity.

Cluster under review: {cluster_skills}

Read these SKILL.md files: {skill_paths}

For each pair, evaluate:
1. Intent difference — do they serve different user goals?
2. Skill type difference — Knowledge vs Automation vs Template vs CLI Wrapper?
3. Freedom level — does one need tight scripts while the other is open-ended?
4. Audience mode — auto-invoked vs user-only?
5. Size risk — would merging create an unwieldy >500 line skill?

Output a structured verdict for each pair:
- Pair: A ↔ B
- Keep-separate score (0-10): [score]
- Key argument for keeping separate: [1-2 sentences]
- What would be lost by merging: [1 sentence]
- Disambiguation suggestion: [how to clarify triggers if keeping both]

Be specific. Cite actual content from the SKILL.md files you read.
```

**Synthesizer prompt:**
```
You are the Synthesizer in a skill curation panel. You are neutral and focused on
what best serves the user.

Cluster under review: {cluster_skills}

Read these SKILL.md files: {skill_paths}

Also consider the Consolidator's analysis:
{consolidator_output}

And the Preservationist's analysis:
{preservationist_output}

For each pair, produce a final recommendation:
- Pair: A ↔ B
- Recommendation: MERGE / KEEP / SPLIT / RETIRE
- Confidence: High / Medium / Low
- Reasoning: [2-3 sentences weighing both perspectives]
- If MERGE: proposed name and migration notes
- If KEEP: trigger disambiguation needed?
- Dissenting view worth noting: [1 sentence]

Output a summary table at the end with all recommendations.
```

#### Execution Pattern

```
Step 2a: Launch Consolidator + Preservationist in PARALLEL (both read SKILL.md files)
Step 2b: Wait for both to complete
Step 2c: Launch Synthesizer with both outputs as input
Step 2d: Collect final recommendations
```

Use the Task tool with `subagent_type: "general-purpose"` for all three agents.
The Consolidator and Preservationist can run simultaneously. The Synthesizer must wait
for both to finish since it needs their output.

For large inventories with many clusters, process clusters in parallel batches — one
3-agent panel per cluster, multiple clusters simultaneously.

### Step 3: Present to User

Format the Synthesizer's output into a decision table:

```markdown
## Curation Recommendations

| Cluster | Skills | Verdict | Confidence | Key Reason |
|---------|--------|---------|------------|------------|
| 1 | A, B, C | MERGE → D | High | Same domain, 80% workflow overlap |
| 2 | E, F | KEEP | Medium | Different intent despite keyword overlap |
| ... | ... | ... | ... | ... |

### Details per cluster
[Expand with Consolidator/Preservationist highlights for each]
```

Include enough context from both perspectives so the user can make an informed decision.
**Do not auto-execute. Wait for explicit user approval per cluster.**

### Step 4: Execute (After Approval)

#### Merge Procedure (A + B → C)

1. Create archive: `mkdir -p ~/.claude/skills/.archived`
2. Copy originals to archive: `cp -r A .archived/A-$(date +%Y%m%d)`
3. Decide which skill directory to keep as C (typically the broader one)
4. Merge SKILL.md content:
   - Union all trigger phrases in description
   - Union tools lists
   - Merge workflow sections (deduplicate shared steps)
   - Combine reference files and scripts
5. Remove the absorbed skill directory
6. Validate: run `quick_validate.py C` from the create-skill skill (`~/.claude/skills/create-skill/`)

#### Split Procedure (X → Y + Z)

1. Archive original: `cp -r X .archived/X-$(date +%Y%m%d)`
2. Create new skill directory for the split-off portion
3. Partition trigger phrases — no overlapping triggers between Y and Z
4. Move relevant scripts and references to each side
5. Validate both Y and Z

#### Retire Procedure

1. Archive: `mv X .archived/X-$(date +%Y%m%d)`
2. Search other skills for cross-references to X and update them

### Step 5: Verify

After all changes, re-run the analysis to confirm:
- No new high-overlap clusters introduced
- Total skill count reduced (or unchanged if only splitting)
- All remaining skills pass validation

## Quick Reference

### Known False Positives

| Pattern | Why It's False | Example |
|---------|----------------|---------|
| Generic keyword overlap | "create", "write", "build" appear everywhere | content-writer ↔ mcp-builder |
| Same tool profile | Many skills use Bash+Read+Write+Edit | pdf ↔ docx |
| Mentor suffix | Naming convention, not domain overlap | model-mentor ↔ openclaw-mentor |

### Known Cluster Patterns

| Pattern | Typical Action |
|---------|---------------|
| Multiple CLI headless wrappers | Consider merge if workflows are near-identical |
| Multiple skills for same product | Evaluate by skill type (knowledge vs automation) |
| "Design" vs "Engineering" | Usually keep separate (different freedom levels) |
| File format skills (pdf/docx/xlsx/pptx) | Usually keep separate (different domain objects) |
| "Writing" family (content/marketing/docs) | Usually keep separate (different intent) |
| Meta-skills (create/optimize/curate) | Usually keep separate (different lifecycle stages) |

## Continuous Improvement

This skill evolves with each use. After every invocation:

1. **Reflect** — Identify what worked, what caused friction, and any unexpected issues
2. **Record** — Append a concise lesson to `lessons.md` in this skill's directory
3. **Refine** — When a pattern recurs (2+ times), update SKILL.md directly

### lessons.md Entry Format

```
### YYYY-MM-DD — Brief title
- **Friction**: What went wrong or was suboptimal
- **Fix**: How it was resolved
- **Rule**: Generalizable takeaway for future invocations
```

Accumulated lessons signal when to run `/skill-optimizer` for a deeper structural review.

## Additional Resources

### Reference Files
- **`references/merge-criteria.md`** — Decision framework with scoring signals,
  flowchart, and migration checklist

### Scripts
- **`scripts/analyze.py`** — Scan all skills, compute overlap scores, identify clusters.
  Usage: `python3 analyze.py [--skills-dir DIR] [--json] [--threshold N]`
