---
name: spark
description: Initialize Codex AI PPT from a one-line idea or topic. Use when the user starts with "/codex-ai-ppt:spark" or otherwise provides only a theme and needs Codex to create a reviewable contract, outline, page descriptions, image plan, and a ready-to-paste /goal handoff for image-based PPT generation.
---

# Codex AI PPT Spark

Use this skill only for `/codex-ai-ppt:spark` or equivalent requests where the user provides an idea, topic, audience goal, or one-sentence PPT brief but not a complete outline.

## Required References

Read these shared files before creating artifacts:

- `../../references/style-source-gate.md`
- `../../references/codex-ai-ppt-workflow.md`
- `../../references/confirmation-gates.md`
- `../../references/prompt-patterns.md`

## Workflow

1. Run Style Source Gate first. If the user did not clearly choose a template image or a style description, ask the fixed two-option question from `style-source-gate.md` and stop there.
2. Create a local run directory under the caller's project as `.codex-ai-ppt/<slug>-NNN/`; never write generated run artifacts into the plugin directory.
3. Call `python3 /Users/hola/Desktop/aippt/plugins/codex-ai-ppt/scripts/ppt_goal.py init --mode spark` with title, aspect, language, page count, and confirmed style-source fields.
4. Prepare and show Project Contract Gate. Do not treat silence as approval.
5. After explicit approval, write `CONTRACT.md` through `python3 /Users/hola/Desktop/aippt/plugins/codex-ai-ppt/scripts/ppt_goal.py write-artifact --stage contract --stdin`.
6. Generate `OUTLINE.md` from the idea. Include stable slide IDs (`page-001`, `page-002`, ...), page titles, and concise bullets.
7. Show Outline Gate with exactly these choices: accept, manually modify, or refine with natural language.
8. After approval, write `OUTLINE.md` through `python3 /Users/hola/Desktop/aippt/plugins/codex-ai-ppt/scripts/ppt_goal.py write-artifact --stage outline --stdin`.
9. Generate `DESCRIPTIONS.md`; rendered text in this file is final slide text, not commentary.
10. Show Description Gate with per-page summary plus risks such as dense text, weak cover, or missing image references.
11. After approval, write `DESCRIPTIONS.md`, then create `IMAGE_PLAN.md` and `prompts/page-NNN.md`.
12. Show Image Plan Gate with page count, expected image calls, and whether to generate all pages.
13. After approval, validate style source and image plan, write `GOAL.md`, and output exactly one ready-to-paste `/goal` line.

## Guardrails

- Do not output `/goal` before Style Source Gate and all downstream confirmation gates have explicit approval.
- Do not generate final slide images during initialization.
- Do not assume a default visual source.
- Preserve the user's stated topic and intent in the contract.
