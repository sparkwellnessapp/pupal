import { defineConfig } from 'vitest/config';
import path from 'path';

// PR-2 introduced the first frontend tests (pure-logic: transport/auth policy,
// session/stash arithmetic). B-11 adds a component render test that SSR-renders
// RubricEditor via react-dom/server — no jsdom needed, but it does need the
// AUTOMATIC JSX runtime (react/jsx-runtime), which is what Next uses in the app
// so components never import React. Without this, RubricEditor's internal JSX
// compiles to bare `React.createElement` and throws "React is not defined".
export default defineConfig({
  esbuild: { jsx: 'automatic', jsxImportSource: 'react' },
  test: {
    environment: 'node',
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
  },
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
});
