// ESLint 9 flat config. This replaces `.eslintrc.cjs`, which ESLint 9 no longer
// reads: the eslintrc format and its `extends` strings only apply in the legacy
// configuration system.
//
// The same rule sets as before, in the same order, so the only thing this
// migration changes is *how* the config is expressed. Note that `env` has no
// equivalent here and needs none: `env.browser` existed to stop `no-undef`
// flagging `document`, `localStorage` and friends, and typescript-eslint's
// `eslint-recommended` already turns `no-undef` off for `.ts`/`.tsx` (TypeScript
// does that check itself), so the setting was inert in the eslintrc too. Adding
// the `globals` package to reproduce it would be a dependency whose only effect
// is on a rule that is disabled for every file this project lints.
//
// Blocks are applied in order and later ones win, which is how the eslintrc
// `extends` array behaved: `eslint:recommended` first, then the TypeScript
// rules that override some of it, then the plugin presets.
import js from "@eslint/js";
import tseslint from "@typescript-eslint/eslint-plugin";
import reactHooks from "eslint-plugin-react-hooks";
import jsxA11y from "eslint-plugin-jsx-a11y";
import reactRefresh from "eslint-plugin-react-refresh";
import globals from "globals";

export default [
  // `dist` is build output, the way `ignorePatterns` said before. The old
  // `.eslintrc.cjs` entry is gone with the file.
  { ignores: ["dist"] },

  js.configs.recommended,

  // An array of three blocks, so it spreads: `base` (which is what installs the
  // TypeScript parser and `sourceType: "module"`), `eslint-recommended` (turning
  // off the core rules TypeScript subsumes), and the `recommended` rule set.
  ...tseslint.configs["flat/recommended"],

  reactHooks.configs["recommended-latest"],

  // Accessibility is a lint rule here rather than a review habit: an unlabelled
  // input or a click handler on a `<div>` fails the build, so it is caught while
  // the component is being written instead of in an audit.
  jsxA11y.flatConfigs.recommended,

  {
    // Our own Node scripts (`scripts/audit-production.mjs` is the one that
    // exists). Flat config lints `.mjs` by default, whereas the old
    // `--ext ts,tsx` *replaced* the default extension list and so never looked
    // at them — this block is what makes that file lint clean rather than
    // unlooked-at. `globals.node` is declared here and only here; it has no
    // place in the browser code below.
    files: ["scripts/**/*.{js,mjs}"],
    languageOptions: { globals: globals.node },
  },

  {
    files: ["**/*.{ts,tsx}"],
    plugins: { "react-refresh": reactRefresh },
    rules: {
      // This plugin has no shipped flat preset at 0.4.x, so the rule is wired up
      // by hand — same name, same options, as the eslintrc had.
      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
    },
  },
];
