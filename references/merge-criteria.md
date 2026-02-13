# Merge & Split Decision Criteria

## TOC
- [The Goldilocks Principle](#the-goldilocks-principle)
- [Merge Signals](#merge-signals)
- [Keep-Separate Signals](#keep-separate-signals)
- [Split Signals](#split-signals)
- [Decision Flowchart](#decision-flowchart)
- [Migration Checklist](#migration-checklist)

## The Goldilocks Principle

A skill should be **one coherent capability domain** — not a single command, not an entire
discipline.

| Too Small (Merge Up) | Just Right | Too Large (Split) |
|-----------------------|------------|-------------------|
| "Add watermark to PDF" | "PDF processing" | "Document processing" |
| "Generate Mermaid flowchart" | "Diagram generation" | "All visualization" |
| "Write email subject line" | "Marketing copy" | "All writing" |
| "Run claude -p" | "CLI headless wrapper" | "All CLI operations" |

**Litmus test**: If two skills share >60% of their procedural knowledge and a user would
reasonably expect them to be "the same thing", they should merge.

## Merge Signals

Score each signal 0-2. Total >= 5 → strong merge candidate.

| Signal | Weight | Description |
|--------|--------|-------------|
| **Trigger collision** | 2 | Users would say the same phrase for either skill |
| **Shared workflow** | 2 | >50% of steps are identical or near-identical |
| **Same tools** | 1 | Both use the same primary tools (Playwright, Bash, etc.) |
| **Same domain object** | 2 | Both operate on the same thing (NotebookLM, a file format, etc.) |
| **Sequential dependency** | 1 | Skill A is almost always used before/after Skill B |
| **Keyword overlap > 0.4** | 1 | analyze.py keyword_sim > 0.4 |

## Keep-Separate Signals

Any of these can override merge signals:

| Signal | Description |
|--------|-------------|
| **Different skill type** | One is Knowledge, other is Automation (see create-skill types) |
| **Different freedom level** | One needs tight scripts, other is open-ended guidance |
| **Different audience mode** | One is auto-invoked, other is user-only |
| **Size explosion** | Merged skill would exceed 500-line SKILL.md limit |
| **Distinct trigger context** | Despite keyword overlap, users mean different things |

## Split Signals

A skill should split when:

1. **SKILL.md > 400 lines** and has clearly separable sections
2. **Two distinct user intents** that never co-occur
3. **Different tool requirements** within the same skill
4. **One part changes frequently**, other is stable

## Decision Flowchart

```
Start with pair (A, B)
  │
  ├─ Do they operate on the same domain object? ──No──→ Keep separate
  │   │Yes
  ├─ Would a user expect them as "one thing"? ──No──→ Keep separate
  │   │Yes
  ├─ Would merged SKILL.md exceed 500 lines? ──Yes──→ Merge with references
  │   │No                                              (lean SKILL.md + ref files)
  ├─ Do they have different skill types? ──Yes──→ Consider: keep separate
  │   │No                                        or merge with sections
  └─ MERGE
```

## Migration Checklist

When merging skills A + B → C:

1. **Preserve all trigger phrases** from both A and B in C's description
2. **Union the tools lists** (deduplicate)
3. **Keep the higher version number** as starting point for C
4. **Migrate scripts**: Copy unique scripts, merge overlapping ones
5. **Migrate references**: Same approach as scripts
6. **Update cross-references**: Search all other skills for mentions of A or B
7. **Archive originals**: Move A and B to `~/.claude/skills/.archived/` (don't delete)
8. **Validate**: Run quick_validate.py on C
9. **Test**: Try 2-3 trigger phrases from both original skills

When splitting skill X → Y + Z:

1. **Partition trigger phrases** clearly between Y and Z
2. **No shared triggers** — if ambiguous, pick one and add disambiguation note
3. **Shared scripts/references** can be symlinked or duplicated
4. **Update description** of both to explicitly exclude the other's domain
