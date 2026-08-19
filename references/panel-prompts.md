# Panel Discussion Prompt Templates

Use these verbatim prompt templates for the 3-agent panel in Step 2.
Replace `{cluster_skills}`, `{skill_paths}`, `{consolidator_output}`, `{preservationist_output}`.

## Consolidator Prompt

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

## Preservationist Prompt

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

## Synthesizer Prompt

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

## Execution Pattern

```
Step 2a: Launch Consolidator + Preservationist in PARALLEL
Step 2b: Wait for both to complete
Step 2c: Launch Synthesizer with both outputs as input
Step 2d: Collect final recommendations
```

Use `subagent_type: "general-purpose"` for all three agents.
For large inventories: process clusters in parallel batches — one 3-agent panel per cluster.
