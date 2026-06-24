#!/usr/bin/env node
import fs from "node:fs/promises";
import { createRequire } from "node:module";

function slideSize(aspect) {
  if (aspect === "4:3") return { width: 1024, height: 768 };
  if (aspect === "1:1") return { width: 1024, height: 1024 };
  return { width: 1280, height: 720 };
}

async function main() {
  const specPath = process.argv[2];
  if (!specPath) {
    throw new Error("usage: export_pptx_artifact.mjs <spec.json>");
  }
  const spec = JSON.parse(await fs.readFile(specPath, "utf8"));
  const requireFromRuntime = createRequire(`${process.cwd()}/package.json`);
  const { Presentation, PresentationFile } = await import(
    requireFromRuntime.resolve("@oai/artifact-tool")
  );
  const size = slideSize(spec.aspect);
  const presentation = Presentation.create({ slideSize: size });

  for (const page of spec.pages) {
    const slide = presentation.slides.add();
    const imageBytes = await fs.readFile(page.image);
    const blob = imageBytes.buffer.slice(
      imageBytes.byteOffset,
      imageBytes.byteOffset + imageBytes.byteLength,
    );
    slide.images.add({
      blob,
      contentType: "image/png",
      alt: page.title || page.slide_id,
      fit: "cover",
      position: { left: 0, top: 0, width: size.width, height: size.height },
    });
  }

  const pptx = await PresentationFile.exportPptx(presentation);
  await pptx.save(spec.out);
}

main().catch((error) => {
  console.error(error && error.stack ? error.stack : String(error));
  process.exitCode = 1;
});
