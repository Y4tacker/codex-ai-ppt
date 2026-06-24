# Confirmation Gates

Silence is never confirmation. Ask for explicit approval at every gate, and stop when the user wants edits.

## Common Gate 0: Style Source Gate

Must pass before contract finalization, image plan creation, or `/goal` output.

## Spark Gates

1. Project Contract Gate: confirm theme, audience, page range, language, aspect, style source, and references.
2. Outline Gate: show page titles and key bullets. Offer exactly: accept, manually modify, refine with natural language.
3. Description Gate: show per-page description summaries and risks such as dense text, weak cover, or missing image references.
4. Image Plan Gate: confirm page count, expected image calls, and whether to generate all pages. After approval, write `GOAL.md` and output `/goal`.

## Outline Gates

1. Project Contract Gate: confirm title, audience, language, aspect, style source, and raw outline as source material.
2. Parsed Outline Gate: show parsed outline; do not rewrite unless the user requests refinement.
3. Description Gate.
4. Image Plan Gate.

## Brief Gates

1. Project Contract Gate: confirm title, audience, language, aspect, style source, and raw page descriptions as source material.
2. Description Gate: show parsed descriptions; ask when page boundaries or titles are ambiguous.
3. Image Plan Gate.

## Approval Language

When asking for approval, ask the user to choose one of: accept, modify manually, or refine. For brief mode description parsing, use: accept, modify manually, or clarify page boundaries.
