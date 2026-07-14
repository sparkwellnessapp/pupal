import { defineConfig } from 'vitest/config';
import path from 'path';

// PR-2 introduced the first frontend tests. Pure-logic only (no jsdom, no React
// rendering): the things worth pinning here are the transport/auth POLICY and the
// session/stash arithmetic, all of which are plain functions.
export default defineConfig({
  test: {
    environment: 'node',
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
  },
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
});
