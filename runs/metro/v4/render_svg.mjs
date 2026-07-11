import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const sharp = require("sharp");

const [input, output, widthArg] = process.argv.slice(2);
if (!input || !output) {
  console.error("usage: node render_svg.mjs INPUT.svg OUTPUT.png [width]");
  process.exit(2);
}

const width = widthArg ? Number(widthArg) : 1800;
const svg = fs.readFileSync(input);
await sharp(svg, { density: 144 }).resize({ width, withoutEnlargement: false }).png({ compressionLevel: 9 }).toFile(output);
console.log(`${path.basename(input)} -> ${path.basename(output)} (${width}px)`);
