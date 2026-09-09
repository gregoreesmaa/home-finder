// Flat ESLint config: recommended JS + TS rules for apps + shared packages.
import js from "@eslint/js";
import tseslint from "typescript-eslint";

export default tseslint.config(
  {
    ignores: [
      "**/node_modules/**",
      "**/.next/**",
      "**/dist/**",
      "**/coverage/**",
      "**/playwright-report/**",
      "**/test-results/**",
    ],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    // Allow the omit-via-destructure pattern: const { dropped, ...rest } = x;
    rules: { "@typescript-eslint/no-unused-vars": ["error", { ignoreRestSiblings: true }] },
  },
  {
    // Node + browser-touching automation scripts (no new dep for globals).
    files: ["scripts/**/*.mjs"],
    languageOptions: {
      globals: {
        console: "readonly",
        process: "readonly",
        fetch: "readonly",
        document: "readonly",
      },
    },
  },
);
