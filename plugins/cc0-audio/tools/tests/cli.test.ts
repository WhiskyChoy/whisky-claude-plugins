import { describe, it, expect } from "bun:test";
import { spawn } from "child_process";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const CLI = join(__dirname, "..", "src", "cli.ts");

/** Run CLI. Set noKey=true to strip all Freesound API key sources. */
function run(args: string[], noKey = false): Promise<{ code: number; stdout: string; stderr: string }> {
  return new Promise((resolve) => {
    const env = { ...process.env };
    if (noKey) {
      delete env.FREESOUND_API_KEY;
      // Prevent loadEnvFile from finding the real key
      env.HOME = "/tmp/cc0-audio-test-no-home";
      env.USERPROFILE = "/tmp/cc0-audio-test-no-home";
    }
    const proc = spawn("bun", ["run", CLI, ...args], { env });
    let stdout = "";
    let stderr = "";
    proc.stdout.on("data", (d: Buffer) => { stdout += d.toString(); });
    proc.stderr.on("data", (d: Buffer) => { stderr += d.toString(); });
    proc.on("close", (code) => resolve({ code: code ?? 1, stdout, stderr }));
  });
}

describe("cc0-audio CLI", () => {
  it("--help exits 0 and shows usage", async () => {
    const r = await run(["--help"]);
    expect(r.code).toBe(0);
    expect(r.stdout).toContain("CC0 Audio");
    expect(r.stdout).toContain("search");
    expect(r.stdout).toContain("download");
    expect(r.stdout).toContain("compress");
    expect(r.stdout).toContain("batch");
    expect(r.stdout).toContain("opengameart");
  });

  it("-h is an alias for --help", async () => {
    const r = await run(["-h"]);
    expect(r.code).toBe(0);
    expect(r.stdout).toContain("CC0 Audio");
  });

  it("no args shows help", async () => {
    const r = await run([]);
    expect(r.code).toBe(0);
    expect(r.stdout).toContain("Usage:");
  });

  it("unknown subcommand errors", async () => {
    const r = await run(["foobar"]);
    expect(r.code).not.toBe(0);
    expect(r.stderr).toContain("Unknown subcommand");
  });

  it("search without query errors", async () => {
    const r = await run(["search"]);
    expect(r.code).not.toBe(0);
    expect(r.stderr).toContain("No search query");
  });

  it("download without target errors", async () => {
    const r = await run(["download"]);
    expect(r.code).not.toBe(0);
    expect(r.stderr).toContain("No sound ID or URL");
  });

  it("compress without input errors", async () => {
    const r = await run(["compress"]);
    expect(r.code).not.toBe(0);
    expect(r.stderr).toContain("No input file");
  });

  it("compress with missing file errors", async () => {
    const r = await run(["compress", "/nonexistent/file.mp3"]);
    expect(r.code).not.toBe(0);
    expect(r.stderr).toContain("not found");
  });

  it("check-urls without URL errors", async () => {
    const r = await run(["check-urls"]);
    expect(r.code).not.toBe(0);
    expect(r.stderr).toContain("No base URL");
  });

  it("batch without manifest errors", async () => {
    const r = await run(["batch"]);
    expect(r.code).not.toBe(0);
    expect(r.stderr).toContain("No manifest file");
  });

  it("search falls back to OGA when no Freesound key", async () => {
    const r = await run(["search", "battle theme"], true);
    expect(r.code).toBe(0);
    expect(r.stdout).toContain("falling back to OpenGameArt");
    expect(r.stdout).toContain("Searching OpenGameArt");
  }, 15000);

  it("search --source oga works directly", async () => {
    const r = await run(["search", "ambient", "--source", "oga"], true);
    expect(r.code).toBe(0);
    expect(r.stdout).toContain("Searching OpenGameArt");
  }, 15000);

  it("download numeric ID without key gives helpful error", async () => {
    const r = await run(["download", "12345"], true);
    expect(r.code).not.toBe(0);
    expect(r.stderr).toContain("Freesound API key required");
    expect(r.stderr).toContain("opengameart.org");
  });
});
