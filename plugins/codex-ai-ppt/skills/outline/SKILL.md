---
name: outline
description: Initialize Codex AI PPT from a structured user outline, such as Markdown headings and bullets. Use when the user starts with "/codex-ai-ppt:outline" and already has titles or sections, wants Codex to preserve the source outline, confirm artifacts, then emit a ready-to-paste /goal handoff for image-based PPT generation.
---

# Codex AI PPT Outline

Use this skill only for `/codex-ai-ppt:outline` or equivalent requests where the user provides structured outline material.

## Required References

Read these shared files before creating artifacts:

- `../../references/style-source-gate.md`
- `../../references/codex-ai-ppt-workflow.md`
- `../../references/confirmation-gates.md`
- `../../references/prompt-patterns.md`

## Workflow

1. Run Style Source Gate first. If the user did not clearly choose a template image or a style description, ask the fixed two-option question from `style-source-gate.md` and stop there.
2. Create `.codex-ai-ppt/<slug>-NNN/` in the caller's project, not in the plugin directory.
3. Call `python3 /Users/hola/Desktop/aippt/plugins/codex-ai-ppt/scripts/ppt_goal.py init --mode outline` with title, aspect, language, and confirmed style-source fields.
4. Create Project Contract Gate. The user's raw outline is source material and must be recorded in the contract.
5. After explicit approval, write `CONTRACT.md` through `python3 /Users/hola/Desktop/aippt/plugins/codex-ai-ppt/scripts/ppt_goal.py write-artifact --stage contract --stdin`.
6. Parse the outline into stable slide IDs and page titles without rewriting, expanding, deleting, or "improving" the user's original wording.
7. Show Parsed Outline Gate. Only accept confirmation or user edits. Enter AI refinement only if the user explicitly asks to refine the outline.
8. After approval, write `OUTLINE.md` through `python3 /Users/hola/Desktop/aippt/plugins/codex-ai-ppt/scripts/ppt_goal.py write-artifact --stage outline --stdin`.
9. Generate `DESCRIPTIONS.md`; rendered text is final slide text, not explanations.
10. Show Description Gate and require explicit approval.
11. Generate `IMAGE_PLAN.md` and `prompts/page-NNN.md`, then show Image Plan Gate.
12. After approval, validate style source and image plan, write `GOAL.md`, and output exactly one ready-to-paste `/goal` line.

## Guardrails

- Never silently rewrite the user's outline.
- If page boundaries are ambiguous, ask before producing descriptions.
- Do not output `/goal` before all required gates are explicitly approved.
- Keep existing slide IDs stable when the user edits the outline; use `python3 /Users/hola/Desktop/aippt/plugins/codex-ai-ppt/scripts/ppt_goal.py smart-merge-outline --stdin` for outline updates after downstream artifacts exist.
