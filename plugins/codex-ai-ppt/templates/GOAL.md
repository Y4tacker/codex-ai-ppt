# Codex AI PPT Executor Protocol

Run directory: `{{run_dir}}`

1. Read `CONTRACT.md`, `OUTLINE.md`, `DESCRIPTIONS.md`, and `IMAGE_PLAN.md`.
2. Treat the artifacts as already confirmed. Do not rewrite the outline, descriptions, page count, or style source, and do not ask new product-decision questions.
3. Run `python3 /Users/hola/Desktop/aippt/plugins/codex-ai-ppt/scripts/ppt_goal.py validate-style-source --run {{run_dir}}`.
4. For each `prompts/page-NNN.md`, render one complete slide PNG with Codex built-in `image_gen` or GPT Images. Do not call external image APIs, do not require `OPENAI_API_KEY`, and do not switch to an imagegen CLI fallback.
5. Locate the selected local PNG. `image_gen` output may land under `$CODEX_HOME/generated_images/...`. If no copyable local image path is available, write `CODEX_AI_PPT_HANDOFF` and stop.
6. Record the image version by calling:

```bash
python3 /Users/hola/Desktop/aippt/plugins/codex-ai-ppt/scripts/ppt_goal.py version-add --run {{run_dir}} --page page-NNN --image <png-path> --prompt prompts/page-NNN.md
```

This copies the final PNG to both `versions/page-NNN/vNNN.png` and `slides/page-NNN.png`.

7. Retry each page at most 3 times. Stop with `CODEX_AI_PPT_HANDOFF` if image generation is unavailable, no copyable PNG exists, or failures remain.
8. Export:

```bash
python3 /Users/hola/Desktop/aippt/plugins/codex-ai-ppt/scripts/ppt_goal.py export-pptx --run {{run_dir}} --out {{run_dir}}/exports/deck.pptx
```

9. Run:

```bash
python3 /Users/hola/Desktop/aippt/plugins/codex-ai-ppt/scripts/ppt_goal.py final-status --run {{run_dir}} --json
```

10. Print `CODEX_AI_PPT_RUN_COMPLETE` only when `ready=true`. If required artifacts, images, export, or validation are unresolved, write `CODEX_AI_PPT_HANDOFF` instead.
