---
name: brief
description: Initialize Codex AI PPT from complete per-page slide descriptions. Use when the user starts with "/codex-ai-ppt:brief" and each page already contains the final text or visual instructions, so Codex should skip normal outline generation, confirm descriptions, then emit a ready-to-paste /goal handoff.
---

# Codex AI PPT Brief

Use this skill only for `/codex-ai-ppt:brief` or equivalent requests where the user already provides complete page descriptions.

## Required References

Read these shared files before creating artifacts:

- `../../references/style-source-gate.md`
- `../../references/codex-ai-ppt-workflow.md`
- `../../references/confirmation-gates.md`
- `../../references/prompt-patterns.md`

## Workflow

1. Run Style Source Gate first. If the user did not clearly choose a template image or a style description, ask the fixed two-option question from `style-source-gate.md` and stop there.
2. Create `.codex-ai-ppt/<slug>-NNN/` in the caller's project, not in the plugin directory.
3. Call `python3 /Users/hola/Desktop/aippt/plugins/codex-ai-ppt/scripts/ppt_goal.py init --mode brief` with title, aspect, language, and confirmed style-source fields.
4. Create Project Contract Gate. The user's page descriptions are core source material and must be recorded in the contract.
5. After explicit approval, write `CONTRACT.md` through `python3 /Users/hola/Desktop/aippt/plugins/codex-ai-ppt/scripts/ppt_goal.py write-artifact --stage contract --stdin`.
6. Parse the user's pages into `DESCRIPTIONS.md`. Prefer page boundaries marked with `--- PAGE ---`, `## 页面标题`, `## page-NNN 标题`, or an equivalent explicit separator. Do not regenerate the content unless the user asks.
7. Reverse-extract a lightweight `OUTLINE.md` with stable slide IDs, page titles, and navigation context only.
8. Show Description Gate. If page count, page boundaries, or page titles are ambiguous, ask for explicit confirmation.
9. After approval, write `OUTLINE.md` and `DESCRIPTIONS.md`.
10. Generate `IMAGE_PLAN.md` and `prompts/page-NNN.md`, then show Image Plan Gate.
11. After approval, validate style source and image plan, write `GOAL.md`, and output exactly one ready-to-paste `/goal` line.

## Guardrails

- Skip normal outline generation, but always maintain a lightweight `OUTLINE.md` for prompt context.
- Do not invent slide text beyond the user's page descriptions unless explicitly requested.
- Do not silently split one long passage into multiple pages and continue to the image plan. Ask the user to confirm page count and boundaries first.
- Do not output `/goal` before Style Source Gate, Project Contract Gate, Description Gate, and Image Plan Gate are explicitly approved.
