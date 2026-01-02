module.exports = {
  root: true,
  env: { node: true, es2022: true },
  extends: ["eslint:recommended"],
  ignorePatterns: [
    "node_modules/**",
    "playwright-report/**",
    "test-results/**",
    ".github/**/runtime_prompt.md",
    "codex-output.md",
    "codex-triage.json"
  ],
  rules: {
    "no-unused-vars": ["error", { "argsIgnorePattern": "^_" }]
  }
};
