// Minimal "build" step for the template.
// Replace this with your real build (e.g., `ng build`, `vite build`, `tsc -p .`, etc.)
import fs from "node:fs";

const requiredFiles = ["package.json", "playwright.config.js"];
for (const f of requiredFiles) {
  if (!fs.existsSync(f)) {
    console.error(`Missing required file: ${f}`);
    process.exit(1);
  }
}
console.log("Build OK (template).");
