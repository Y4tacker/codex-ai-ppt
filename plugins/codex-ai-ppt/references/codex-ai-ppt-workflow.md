# Codex AI PPT Workflow

Use this shared protocol for all Codex AI PPT skills.

## Run Directory

Create artifacts under the caller's project:

```text
.codex-ai-ppt/<slug>-NNN/
  CONTRACT.md
  OUTLINE.md
  DESCRIPTIONS.md
  IMAGE_PLAN.md
  GOAL.md
  STATE.json
  references/template.png
  prompts/page-001.md
  slides/page-001.png
  versions/page-001/v001.png
  exports/deck.pptx
  events.jsonl
  reports/final.md
```

Never store generated run artifacts inside the plugin installation directory.

## CLI

Use the plugin CLI through its absolute script path. `bin/codex-ai-ppt` is a convenience wrapper only; do not depend on it being registered in `PATH`.

Set this value in generated instructions:

```bash
PLUGIN_ROOT=/Users/hola/Desktop/aippt/plugins/codex-ai-ppt
```

Stable commands:

```bash
python3 /Users/hola/Desktop/aippt/plugins/codex-ai-ppt/scripts/ppt_goal.py init --run <run-dir> --mode spark|outline|brief --title <title> --aspect 16:9 --language auto --style-source template_image|style_description
python3 /Users/hola/Desktop/aippt/plugins/codex-ai-ppt/scripts/ppt_goal.py status --run <run-dir> --json
python3 /Users/hola/Desktop/aippt/plugins/codex-ai-ppt/scripts/ppt_goal.py write-artifact --run <run-dir> --stage contract|outline|descriptions|image-plan --stdin
python3 /Users/hola/Desktop/aippt/plugins/codex-ai-ppt/scripts/ppt_goal.py validate --run <run-dir> --stage contract|outline|descriptions|image-plan|images|export
python3 /Users/hola/Desktop/aippt/plugins/codex-ai-ppt/scripts/ppt_goal.py validate-style-source --run <run-dir>
python3 /Users/hola/Desktop/aippt/plugins/codex-ai-ppt/scripts/ppt_goal.py smart-merge-outline --run <run-dir> --stdin
python3 /Users/hola/Desktop/aippt/plugins/codex-ai-ppt/scripts/ppt_goal.py version-add --run <run-dir> --page <slide-id> --image <png-path> --prompt <prompt-path>
python3 /Users/hola/Desktop/aippt/plugins/codex-ai-ppt/scripts/ppt_goal.py version-activate --run <run-dir> --page <slide-id> --version <version-id>
python3 /Users/hola/Desktop/aippt/plugins/codex-ai-ppt/scripts/ppt_goal.py export-pptx --run <run-dir> --out <pptx-path>
python3 /Users/hola/Desktop/aippt/plugins/codex-ai-ppt/scripts/ppt_goal.py final-status --run <run-dir> --json
```

Recommended user-facing entry prefixes are `/codex-ai-ppt:spark`, `/codex-ai-ppt:outline`, and `/codex-ai-ppt:brief`. Treat them as trigger aliases/default prompts, not as actual command registrations.

## Marketplace Setup

For repo-local installation, read the marketplace name after scaffold:

```bash
python3 /Users/hola/.codex/skills/.system/plugin-creator/scripts/read_marketplace_name.py --marketplace-path /Users/hola/Desktop/aippt/.agents/plugins/marketplace.json
```

Check whether that marketplace is installed:

```bash
codex plugin marketplace list
```

If it is already listed as `personal  /Users/hola/Desktop/aippt`, do not add it again. If it is not listed, add the local marketplace root that contains `.agents/plugins/marketplace.json`. In current Codex CLI builds this is the repository root:

```bash
codex plugin marketplace add /Users/hola/Desktop/aippt
```

Then install with the discovered name:

```bash
codex plugin add codex-ai-ppt@<marketplace-name>
```

For the current marketplace file, `<marketplace-name>` is `personal`; install with:

```bash
codex plugin add codex-ai-ppt@personal
```

Only the default personal marketplace at `~/.agents/plugins/marketplace.json` is discovered implicitly.

## State Machine

Project status:

```text
draft -> style_source_confirmed -> contract_confirmed -> outline_confirmed -> descriptions_confirmed -> image_plan_confirmed -> ready_for_goal -> generating_images -> exported -> completed
```

`brief` mode may move from `contract_confirmed` to `descriptions_confirmed`, but still create a lightweight `OUTLINE.md`.

Page status:

```text
planned -> description_ready -> prompt_ready -> queued -> image_generated -> exported
```

Failures must be recorded in `events.jsonl` and surfaced as `CODEX_AI_PPT_HANDOFF` in the `/goal` executor.

## GOAL Handoff

Write full executor instructions into `GOAL.md`, then output exactly one line:

```text
/goal "Read .codex-ai-ppt/<slug>-NNN/GOAL.md and execute it until CODEX_AI_PPT_RUN_COMPLETE appears with final-status ready=true, all confirmed slide prompts rendered through Codex GPT Images, active PNG versions recorded, deck.pptx exported, and validation clean; stop with CODEX_AI_PPT_HANDOFF on unresolved failures."
```

`GOAL.md` must require the executor to:

- Read `CONTRACT.md`, `OUTLINE.md`, `DESCRIPTIONS.md`, and `IMAGE_PLAN.md`.
- Treat these artifacts as already confirmed. Do not rewrite the outline, descriptions, or style source, and do not reopen product decisions with the user.
- Run `python3 /Users/hola/Desktop/aippt/plugins/codex-ai-ppt/scripts/ppt_goal.py validate-style-source --run <run-dir>` first.
- Use Codex built-in `image_gen` or GPT Images for each full slide. Do not call external image APIs, do not require `OPENAI_API_KEY`, and do not switch to an imagegen CLI fallback to control output paths.
- `image_gen` output may land under `$CODEX_HOME/generated_images/...`; locate the selected local PNG and copy it through `python3 /Users/hola/Desktop/aippt/plugins/codex-ai-ppt/scripts/ppt_goal.py version-add`.
- Ensure every selected final image is copied to both `.codex-ai-ppt/<run>/versions/page-NNN/vNNN.png` and `.codex-ai-ppt/<run>/slides/page-NNN.png` via `python3 /Users/hola/Desktop/aippt/plugins/codex-ai-ppt/scripts/ppt_goal.py version-add`.
- If no copyable local image path is available, stop with `CODEX_AI_PPT_HANDOFF`; do not export an empty or partial PPTX.
- Retry each page at most 3 times.
- Stop with `CODEX_AI_PPT_HANDOFF` only when required artifacts are missing, image generation is unavailable or failed, a copyable image path cannot be obtained, PPTX export fails, or validation remains dirty.
- Call `python3 /Users/hola/Desktop/aippt/plugins/codex-ai-ppt/scripts/ppt_goal.py export-pptx`, then `python3 /Users/hola/Desktop/aippt/plugins/codex-ai-ppt/scripts/ppt_goal.py final-status --json`.
- Print `CODEX_AI_PPT_RUN_COMPLETE` only when final status returns `ready=true`.

## PPTX Export

Prefer the Codex Presentations runtime and `@oai/artifact-tool` for PPTX export. This plugin explicitly produces an image-as-slide, image-only artifact, so full-slide bitmaps are the intended output. Each slide should contain exactly one full-slide PNG. The CLI command `export-pptx` remains the state-machine interface; internally it should attempt artifact-tool export first.

The `export-pptx` preferred path must resolve `@oai/artifact-tool` from the Codex bundled runtime. The Node child process must not import `@oai/artifact-tool` from the plugin directory. Use bundled Node:

```text
/Users/hola/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node
```

and run the child process with:

```text
cwd=/Users/hola/.cache/codex-runtimes/codex-primary-runtime/dependencies/node
```

Because ESM bare imports resolve relative to the importing script, the exporter should resolve the package from that cwd with `createRequire(process.cwd() + "/package.json")` before dynamic import. This keeps module resolution anchored in the Codex bundled runtime, not the plugin directory.

If artifact-tool is unavailable or fails, the CLI may use the minimal OOXML fallback, but it must record the fallback reason in `events.jsonl`. OOXML fallback is a fault-tolerance path, not the normal preferred path. If acceptance runs always show `export_pptx_fallback`, treat that as broken artifact-tool module resolution and fix the Node runtime configuration instead of accepting fallback as the final state.

## Validation

Run official plugin and skill validators with a Python environment that includes PyYAML. If `python3` reports `ModuleNotFoundError: No module named 'yaml'`, the validator environment is missing a development dependency; that does not by itself mean the plugin manifest is invalid. Do not vendor PyYAML into the plugin source.

Use these commands:

```bash
# 1. Official plugin validation; requires PyYAML.
python3 /Users/hola/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py \
  /Users/hola/Desktop/aippt/plugins/codex-ai-ppt

# 2. Skill validation; requires PyYAML.
python3 /Users/hola/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  /Users/hola/Desktop/aippt/plugins/codex-ai-ppt/skills/spark

python3 /Users/hola/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  /Users/hola/Desktop/aippt/plugins/codex-ai-ppt/skills/outline

python3 /Users/hola/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  /Users/hola/Desktop/aippt/plugins/codex-ai-ppt/skills/brief

# 3. CLI unit tests; no pytest dependency.
python3 -m unittest /Users/hola/Desktop/aippt/plugins/codex-ai-ppt/tests/test_ppt_goal.py

# 4. Minimal CLI smoke test.
tmp="$(mktemp -d)"
python3 /Users/hola/Desktop/aippt/plugins/codex-ai-ppt/scripts/ppt_goal.py init \
  --run "$tmp/demo-001" \
  --mode spark \
  --title "AI History" \
  --aspect 16:9 \
  --language zh \
  --style-source style_description \
  --style-description "科技现代"

python3 /Users/hola/Desktop/aippt/plugins/codex-ai-ppt/scripts/ppt_goal.py validate-style-source \
  --run "$tmp/demo-001"

printf '## page-001 封面\nVisible text:\nAI 历史\n' | \
python3 /Users/hola/Desktop/aippt/plugins/codex-ai-ppt/scripts/ppt_goal.py write-artifact \
  --run "$tmp/demo-001" \
  --stage descriptions \
  --stdin

python3 /Users/hola/Desktop/aippt/plugins/codex-ai-ppt/scripts/ppt_goal.py validate \
  --run "$tmp/demo-001" \
  --stage descriptions

rm -rf "$tmp"
```
