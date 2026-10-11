import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests",
  workers: 1,
  timeout: 60000,
  use: {
    baseURL: process.env.EPISODE_URL || "http://127.0.0.1:8765",
    headless: true,
    actionTimeout: 10000,
    trace: "retain-on-failure",
  },
  outputDir:
    process.env.EPISODE_TEST_OUTPUT ||
    `${process.env.EPISODE_STORAGE || "/Volumes/External Storage/Episode"}/evidence/browser`,
  reporter: [
    ["list"],
    [
      "json",
      {
        outputFile: `${process.env.EPISODE_STORAGE || "/Volumes/External Storage/Episode"}/evidence/browser-results.json`,
      },
    ],
  ],
});
