import js from "@eslint/js";
import globals from "globals";

export default [
  {
    ignores: [
      "**/node_modules/**",
      "playwright-report/**",
      "test-results/**",
      ".github/**/runtime_prompt.md",
      "frontend/.angular/**",
      "frontend/dist/**",
      "frontend/out-tsc/**",
      "codex-output.md",
      "codex-triage.json"
    ]
  },
  js.configs.recommended,
  {
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
      globals: {
        ...globals.node
      }
    },
    rules: {
      "no-unused-vars": ["error", { argsIgnorePattern: "^_" }]
    }
  }
];
