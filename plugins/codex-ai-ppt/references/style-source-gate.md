# Style Source Gate

Run this gate before any full image plan or `/goal` output for spark, outline, and brief modes.

## Recognition

- Choose `template_image` when the user clearly provides a readable image path, uploads or references a PPT screenshot, says "reference this image", "use this template", or equivalent.
- Choose `style_description` when the user clearly provides a style phrase such as 商务简约, 科技现代蓝黑风, 学术正式, 自然清新, or a longer written visual direction.
- If neither is clear, ask. Do not default.
- If both are present and priority is unclear, ask which is primary.
- If the user chooses template image but has not provided the image yet, ask only for a readable image path, upload, or attached-image reference. Do not enter Project Contract Gate.
- If the user chooses style description but has not provided the text yet, ask only for the style description or preset choice. Do not enter Project Contract Gate.

## Fixed Question

Ask this exact choice prompt:

你希望 PPT 的视觉生成依据是什么？

1. **模板图片**：用户提供一张 PPT 截图、模板图或设计参考图，生成时尽量匹配颜色、字体、版式和设计语言。
2. **风格描述**：用户用文字描述风格，或选择预设风格，再由 GPT Images 按描述生成视觉效果。

## Template Image

After the user has chosen this branch, require a readable path, uploaded image, or explicit attached image reference before initializing the contract. The CLI accepts PNG, JPG, JPEG, and WebP. Copy or record the image under `.codex-ai-ppt/<run>/references/template.*`.

Write this shape in `CONTRACT.md`:

```yaml
style_source:
  type: template_image
  template_image: references/template.png
```

Image prompts must tell GPT Images to match the template image's color palette, typography tendency, layout density, decorative language, and overall atmosphere.

## Style Description

After the user has chosen this branch, require a user-entered style description or one of these presets before initializing the contract: 自然清新, 极简干净, 创意趣味, 渐变鲜艳, 商务简约, 学术正式, 科技现代, 奢华高端.

Write this shape in `CONTRACT.md`:

```yaml
style_source:
  type: style_description
  style_description: "科技现代，深色背景，高对比信息层级，适合 AI 产品汇报"
```

Image prompts must build the visual system from the written style description and must not pretend a template image exists.
