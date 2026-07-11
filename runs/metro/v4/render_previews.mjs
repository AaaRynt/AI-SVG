import fs from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const sharp = require("sharp");

async function render(input, output, width, options = {}) {
  let pipeline = sharp(fs.readFileSync(input), { density: 144 }).resize({ width });
  if (options.extract) pipeline = pipeline.extract(options.extract);
  if (options.grayscale) pipeline = pipeline.grayscale();
  await pipeline.png({ compressionLevel: 9 }).toFile(output);
  process.stdout.write(`${output}\n`);
}

const tasks = [
  ["metro.svg", "preview.png", 3000],
  ["preview_no_labels.svg", "preview_no_labels.png", 3000],
  ["preview_labels_only.svg", "preview_labels_only.png", 3000],
  ["preview_label_boxes.svg", "preview_label_boxes.png", 3000],
  ["metro.svg", "preview_zoom67.png", 2714],
  ["metro.svg", "preview_zoom50.png", 2025],
  ["metro.svg", "preview_grayscale.png", 2400, { grayscale: true }],
  ["metro.svg", "preview_core_area.png", 4050, { extract: { left: 760, top: 430, width: 2180, height: 1760 } }],
  ["geographic_inset.svg", "geographic_inset.png", 1200],
  ["full_candidates/candidate-01/metro.svg", "full_candidates/candidate-01/preview.png", 2400],
  ["full_candidates/candidate-02/metro.svg", "full_candidates/candidate-02/preview.png", 2400],
];

for (const [input, output, width, options] of tasks) {
  await render(input, output, width, options ?? {});
}
