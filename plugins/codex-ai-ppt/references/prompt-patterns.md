# Prompt Patterns

Use one prompt file per slide: `prompts/page-NNN.md`.

## Common Prompt Shape

Each prompt must include:

- Slide ID and title.
- Aspect ratio.
- Final rendered text from `DESCRIPTIONS.md`.
- Visual layout instructions from `IMAGE_PLAN.md`.
- Style source branch.
- Negative constraints: no extra captions, no watermarks, no irrelevant logos, no misspelled text, no explanatory notes outside the slide.

## Template Image Branch

Use when `style_source.type` is `template_image`:

```text
Use the provided template reference image as the primary visual basis. Match its color palette, typography tendency, layout density, spacing rhythm, decorative language, and overall atmosphere while adapting the content for this slide.
```

Do not claim exact font matching unless the font is known.

## Style Description Branch

Use when `style_source.type` is `style_description`:

```text
Build a coherent visual system from this style description: <style_description>. Do not assume any template image exists.
```

## Text Rule

Any slide text in `DESCRIPTIONS.md` is intended to be rendered on the image. Do not add explanatory text, implementation notes, or prompt commentary to the visible slide.
