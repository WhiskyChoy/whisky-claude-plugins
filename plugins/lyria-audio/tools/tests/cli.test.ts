import { describe, it, expect } from "bun:test";
import { spawn } from "child_process";
import { join, dirname } from "path";
import { fileURLToPath } from "url";
import { existsSync, unlinkSync } from "fs";

const __dirname = dirname(fileURLToPath(import.meta.url));
const CLI = join(__dirname, "..", "src", "cli.ts");

// Set TEST_LYRIA_API=1 to run live API tests (requires GEMINI_API_KEY)
const RUN_API_TESTS = process.env.TEST_LYRIA_API === "1";

function run(args: string[]): Promise<{ code: number; stdout: string; stderr: string }> {
  return new Promise((resolve) => {
    const env = { ...process.env };
    if (!RUN_API_TESTS) {
      // Strip API key to prevent accidental real API calls
      delete env.GEMINI_API_KEY;
      env.HOME = "/tmp/lyria-test-no-home";
      env.USERPROFILE = "/tmp/lyria-test-no-home";
    }
    const proc = spawn("bun", ["run", CLI, ...args], { env });
    let stdout = "";
    let stderr = "";
    proc.stdout.on("data", (d: Buffer) => { stdout += d.toString(); });
    proc.stderr.on("data", (d: Buffer) => { stderr += d.toString(); });
    proc.on("close", (code) => resolve({ code: code ?? 1, stdout, stderr }));
  });
}

describe("lyria CLI — help and arg parsing (no API key needed)", () => {
  it("--help exits 0 and shows usage", async () => {
    const r = await run(["--help"]);
    expect(r.code).toBe(0);
    expect(r.stdout).toContain("Lyria");
    expect(r.stdout).toContain("--duration");
    expect(r.stdout).toContain("--bpm");
    expect(r.stdout).toContain("--brightness");
    expect(r.stdout).toContain("--format");
  });

  it("-h is an alias for --help", async () => {
    const r = await run(["-h"]);
    expect(r.code).toBe(0);
    expect(r.stdout).toContain("Lyria");
  });

  it("no args shows help and exits 0", async () => {
    const r = await run([]);
    expect(r.code).toBe(0);
    expect(r.stdout).toContain("Usage:");
  });

  it("--costs runs without error", async () => {
    const r = await run(["--costs"]);
    expect(r.code).toBe(0);
  });
});

describe("lyria CLI — validation errors (no API key needed)", () => {
  it("rejects BPM out of range", async () => {
    const r = await run(["test", "--bpm", "999"]);
    expect(r.code).not.toBe(0);
  });

  it("rejects negative brightness", async () => {
    const r = await run(["test", "--brightness", "-1"]);
    expect(r.code).not.toBe(0);
  });

  it("rejects brightness above 1", async () => {
    const r = await run(["test", "--brightness", "5.0"]);
    expect(r.code).not.toBe(0);
  });

  it("rejects density out of range", async () => {
    const r = await run(["test", "--density", "2.0"]);
    expect(r.code).not.toBe(0);
  });

  it("rejects invalid scale", async () => {
    const r = await run(["test", "--scale", "INVALID_KEY"]);
    expect(r.code).not.toBe(0);
  });

  it("rejects invalid mode", async () => {
    const r = await run(["test", "--mode", "BADMODE"]);
    expect(r.code).not.toBe(0);
  });
});

// ── Live API tests (opt-in: TEST_LYRIA_API=1 bun test) ─────────────────────
// These actually generate audio and require a valid GEMINI_API_KEY.
// Skipped by default on CI and local runs.

const apiDescribe = RUN_API_TESTS ? describe : describe.skip;

apiDescribe("lyria CLI — live API (TEST_LYRIA_API=1)", () => {
  const OUTPUT_DIR = join(__dirname, "..", "test-output");
  const OUTPUT_FILE = join(OUTPUT_DIR, "api-test.wav");

  it("generates a short WAV file", async () => {
    // Clean up from previous runs
    if (existsSync(OUTPUT_FILE)) unlinkSync(OUTPUT_FILE);

    const r = await run([
      "short ambient test tone",
      "--duration", "5",
      "--format", "wav",
      "-o", "api-test",
      "-d", OUTPUT_DIR,
    ]);
    expect(r.code).toBe(0);
    expect(existsSync(OUTPUT_FILE)).toBe(true);

    // Clean up
    if (existsSync(OUTPUT_FILE)) unlinkSync(OUTPUT_FILE);
  }, 60000); // 60s timeout for WebSocket streaming
});
