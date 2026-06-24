# codex-ai-ppt Marketplace

This repository is a Codex plugin marketplace for `codex-ai-ppt`.

## Install

Add this repository as a marketplace:

```bash
codex plugin marketplace add Y4tacker/codex-ai-ppt --ref main
```

Then install the plugin from that marketplace:

```bash
codex plugin add codex-ai-ppt@codex-ai-ppt
```

## Layout

```text
.agents/plugins/marketplace.json
plugins/codex-ai-ppt/
  .codex-plugin/plugin.json
  skills/
  references/
  scripts/
  templates/
  tests/
```

The marketplace manifest lives at `.agents/plugins/marketplace.json`. The plugin package lives at `plugins/codex-ai-ppt`.

See [plugins/codex-ai-ppt/README.md](plugins/codex-ai-ppt/README.md) for plugin usage, modes, validation, and runtime details.
