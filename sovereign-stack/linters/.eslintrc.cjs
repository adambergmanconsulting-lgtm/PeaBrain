/* ESLint 8 + TS: smoke-checking generated snippets */
module.exports = {
  root: true,
  env: { es2022: true, node: true, browser: true },
  ignorePatterns: [],
  parser: "@typescript-eslint/parser",
  parserOptions: { ecmaVersion: "latest", sourceType: "module" },
  plugins: ["@typescript-eslint"],
  rules: {
    "no-undef": "off",
    "@typescript-eslint/no-unused-vars": "off",
  },
};
