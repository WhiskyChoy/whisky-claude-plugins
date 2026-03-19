#!/usr/bin/env bun
/**
 * CC0 Audio Sourcing CLI
 * Search, download, and compress CC0-licensed audio from Freesound.org.
 *
 * Usage:
 *   cc0-audio search "dark fantasy ambient loop"
 *   cc0-audio download 12345 -o ambient
 *   cc0-audio compress input.wav --preset bgm
 *   cc0-audio check-urls https://example.com/audio
 *   cc0-audio batch manifest.json
 */

import { writeFile, mkdir, readFile } from "fs/promises";
import { join, extname, basename, dirname } from "path";
import { existsSync, readFileSync, createWriteStream } from "fs";
import { spawn } from "child_process";
import { fileURLToPath } from "url";
import { homedir } from "os";

// ---------------------------------------------------------------------------
// Environment / API key resolution
// Priority: --api-key flag > FREESOUND_API_KEY env var > .env in cwd >
// .env next to this script > ~/.cc0-audio/.env
// ---------------------------------------------------------------------------

function loadEnvFile(path: string): void {
  if (!existsSync(path)) return;
  const content = readFileSync(path, "utf-8");
  for (const line of content.split("\n")) {
    const trimmed = line.trim();
    if (trimmed && !trimmed.startsWith("#")) {
      const [key, ...valueParts] = trimmed.split("=");
      const value = valueParts.join("=").replace(/^["']|["']$/g, "");
      if (key && value && !process.env[key]) {
        process.env[key] = value;
      }
    }
  }
}

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

loadEnvFile(join(process.cwd(), ".env"));
loadEnvFile(join(__dirname, "..", ".env"));
loadEnvFile(join(homedir(), ".cc0-audio", ".env"));

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const FREESOUND_API = "https://freesound.org/apiv2";

const COMPRESS_PRESETS: Record<string, string[]> = {
  bgm:   ["-c:a", "libmp3lame", "-ac", "1", "-q:a", "5", "-ar", "44100"],
  voice: ["-c:a", "libmp3lame", "-ac", "1", "-q:a", "6", "-ar", "22050"],
};

const LICENSE_FILTERS: Record<string, string> = {
  cc0:   'license:"Creative Commons 0"',
  "cc-by": 'license:"Attribution"',
  any:   "",
};

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface FreesoundResult {
  id: number;
  name: string;
  duration: number;
  license: string;
  tags: string[];
  previews?: Record<string, string>;
}

interface FreesoundSearchResponse {
  count: number;
  results: FreesoundResult[];
}

interface BatchEntry {
  query: string;
  preset?: string;
  output?: string;
  duration?: number;
}

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

function runCommand(cmd: string, args: string[]): Promise<string> {
  return new Promise((resolve, reject) => {
    const proc = spawn(cmd, args);
    let stdout = "";
    let stderr = "";
    proc.stdout.on("data", (data: Buffer) => {
      stdout += data.toString();
    });
    proc.stderr.on("data", (data: Buffer) => {
      stderr += data.toString();
    });
    proc.on("close", (code: number | null) => {
      if (code === 0) resolve(stdout.trim());
      else reject(new Error(`${cmd} failed (exit ${code}): ${stderr}`));
    });
    proc.on("error", (err: Error) => {
      reject(
        new Error(
          `Failed to run ${cmd}: ${err.message}. Is it installed?`
        )
      );
    });
  });
}

function resolveApiKey(flagKey: string | undefined): string | undefined {
  return flagKey || process.env.FREESOUND_API_KEY;
}

function requireApiKey(flagKey: string | undefined): string {
  const key = resolveApiKey(flagKey);
  if (!key) {
    console.error("\x1b[31mError:\x1b[0m FREESOUND_API_KEY is required.");
    console.error("");
    console.error("Set it one of these ways:");
    console.error("  1. Export:    export FREESOUND_API_KEY=your_key");
    console.error("  2. .env:     Create .env with FREESOUND_API_KEY=your_key");
    console.error("  3. Flag:     cc0-audio search \"query\" --api-key your_key");
    console.error("  4. Config:   mkdir -p ~/.cc0-audio && echo 'FREESOUND_API_KEY=your_key' > ~/.cc0-audio/.env");
    console.error("");
    console.error("Get a key at: https://freesound.org/apiv2/apply/");
    process.exit(1);
  }
  return key;
}

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return m > 0 ? `${m}m${s.toString().padStart(2, "0")}s` : `${s}s`;
}

async function downloadFile(url: string, outputPath: string): Promise<void> {
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Download failed: ${res.status} ${res.statusText} — ${url}`);
  }
  const buffer = Buffer.from(await res.arrayBuffer());
  await writeFile(outputPath, buffer);
}

// ---------------------------------------------------------------------------
// Subcommands
// ---------------------------------------------------------------------------

async function cmdSearch(args: string[]): Promise<void> {
  let query = "";
  let source = "freesound";
  let license = "cc0";
  let maxDuration: number | undefined;
  let apiKeyFlag: string | undefined;

  let i = 0;
  while (i < args.length) {
    const arg = args[i];
    if (arg === "--source") {
      source = args[++i];
    } else if (arg === "--license") {
      license = args[++i];
    } else if (arg === "--duration") {
      maxDuration = parseFloat(args[++i]);
    } else if (arg === "--api-key") {
      apiKeyFlag = args[++i];
    } else if (!arg.startsWith("-")) {
      query = arg;
    }
    i++;
  }

  if (!query) {
    console.error("\x1b[31mError:\x1b[0m No search query provided.");
    console.error("Usage: cc0-audio search \"dark fantasy ambient loop\"");
    process.exit(1);
  }

  const apiKey = requireApiKey(apiKeyFlag);

  console.log(`\x1b[36m[cc0-audio]\x1b[0m Searching Freesound...`);
  console.log(`\x1b[90mQuery: ${query}\x1b[0m`);
  if (maxDuration) console.log(`\x1b[90mMax duration: ${maxDuration}s\x1b[0m`);
  console.log("");

  const licenseFilter = LICENSE_FILTERS[license] || "";
  const durationFilter = maxDuration ? ` duration:[0 TO ${maxDuration}]` : "";
  const filter = (licenseFilter + durationFilter).trim();

  const params = new URLSearchParams({
    query,
    token: apiKey,
    fields: "id,name,duration,previews,license,tags",
    page_size: "15",
  });
  if (filter) params.set("filter", filter);

  const url = `${FREESOUND_API}/search/text/?${params}`;
  const res = await fetch(url);

  if (!res.ok) {
    const body = await res.text();
    console.error(`\x1b[31mFreesound API error:\x1b[0m ${res.status} — ${body}`);
    process.exit(1);
  }

  const data: FreesoundSearchResponse = await res.json();

  if (data.results.length === 0) {
    console.log("\x1b[33mNo results found.\x1b[0m Try a different query or broader license filter.");
    return;
  }

  console.log(`\x1b[32mFound ${data.count} results\x1b[0m (showing ${data.results.length}):\n`);

  for (const r of data.results) {
    const previewUrl = r.previews?.["preview-lq-mp3"] || r.previews?.["preview-hq-mp3"] || "—";
    const tags = r.tags?.slice(0, 5).join(", ") || "";
    console.log(`  \x1b[33m#${r.id}\x1b[0m  ${r.name}`);
    console.log(`  \x1b[90m  Duration: ${formatDuration(r.duration)}  |  License: ${r.license}\x1b[0m`);
    if (tags) console.log(`  \x1b[90m  Tags: ${tags}\x1b[0m`);
    console.log(`  \x1b[90m  Preview: ${previewUrl}\x1b[0m`);
    console.log("");
  }
}

async function cmdDownload(args: string[]): Promise<string> {
  let target = "";
  let output = "";
  let outputDir = process.cwd();
  let format = "";
  let apiKeyFlag: string | undefined;

  let i = 0;
  while (i < args.length) {
    const arg = args[i];
    if (arg === "-o" || arg === "--output") {
      output = args[++i];
    } else if (arg === "-d" || arg === "--dir") {
      outputDir = args[++i];
    } else if (arg === "--format") {
      format = args[++i];
    } else if (arg === "--api-key") {
      apiKeyFlag = args[++i];
    } else if (!arg.startsWith("-")) {
      target = arg;
    }
    i++;
  }

  if (!target) {
    console.error("\x1b[31mError:\x1b[0m No sound ID or URL provided.");
    console.error("Usage: cc0-audio download 12345 -o ambient");
    process.exit(1);
  }

  if (!existsSync(outputDir)) {
    await mkdir(outputDir, { recursive: true });
  }

  const isNumeric = /^\d+$/.test(target);

  if (isNumeric) {
    // Freesound download by ID
    const apiKey = requireApiKey(apiKeyFlag);
    const soundId = target;

    // First get sound info for the name
    console.log(`\x1b[36m[cc0-audio]\x1b[0m Fetching sound #${soundId} info...`);
    const infoUrl = `${FREESOUND_API}/sounds/${soundId}/?token=${apiKey}&fields=id,name,duration,type,license,previews,download`;
    const infoRes = await fetch(infoUrl);

    if (!infoRes.ok) {
      const body = await infoRes.text();
      console.error(`\x1b[31mFreesound API error:\x1b[0m ${infoRes.status} — ${body}`);
      process.exit(1);
    }

    const info = await infoRes.json() as any;
    console.log(`\x1b[90mName: ${info.name}\x1b[0m`);
    console.log(`\x1b[90mDuration: ${formatDuration(info.duration)}  |  License: ${info.license}\x1b[0m`);

    // Use preview URL (no OAuth needed) or download URL
    const ext = format || info.type || "mp3";
    const fileName = output ? `${output}.${ext}` : `${info.name || `freesound-${soundId}`}.${ext}`;
    const outputPath = join(outputDir, fileName);

    // Try HQ preview first (no OAuth required), fall back to download endpoint
    const previewUrl = info.previews?.["preview-hq-mp3"];
    if (previewUrl) {
      console.log(`\x1b[36m[cc0-audio]\x1b[0m Downloading HQ preview...`);
      await downloadFile(previewUrl, outputPath);
    } else if (info.download) {
      console.log(`\x1b[36m[cc0-audio]\x1b[0m Downloading original...`);
      const dlUrl = `${info.download}?token=${apiKey}`;
      await downloadFile(dlUrl, outputPath);
    } else {
      console.error("\x1b[31mError:\x1b[0m No download URL available for this sound.");
      process.exit(1);
    }

    console.log(`\x1b[32m[cc0-audio]\x1b[0m Saved: ${outputPath}`);
    return outputPath;
  } else {
    // Direct URL download
    const url = target;
    const ext = format || extname(url).replace(".", "") || "mp3";
    const fileName = output ? `${output}.${ext}` : `download-${Date.now()}.${ext}`;
    const outputPath = join(outputDir, fileName);

    console.log(`\x1b[36m[cc0-audio]\x1b[0m Downloading from URL...`);
    console.log(`\x1b[90m${url}\x1b[0m`);

    await downloadFile(url, outputPath);

    console.log(`\x1b[32m[cc0-audio]\x1b[0m Saved: ${outputPath}`);
    return outputPath;
  }
}

async function cmdCompress(args: string[]): Promise<string> {
  let input = "";
  let output = "";
  let outputDir = process.cwd();
  let preset = "bgm";
  let duration: number | undefined;
  let ffmpegArgs: string | undefined;

  let i = 0;
  while (i < args.length) {
    const arg = args[i];
    if (arg === "-o" || arg === "--output") {
      output = args[++i];
    } else if (arg === "-d" || arg === "--dir") {
      outputDir = args[++i];
    } else if (arg === "--preset") {
      preset = args[++i];
    } else if (arg === "--duration") {
      duration = parseFloat(args[++i]);
    } else if (arg === "--ffmpeg-args") {
      ffmpegArgs = args[++i];
    } else if (!arg.startsWith("-")) {
      input = arg;
    }
    i++;
  }

  if (!input) {
    console.error("\x1b[31mError:\x1b[0m No input file provided.");
    console.error("Usage: cc0-audio compress input.wav --preset bgm");
    process.exit(1);
  }

  const inputPath = input.startsWith("/") || input.match(/^[A-Z]:/)
    ? input
    : join(process.cwd(), input);

  if (!existsSync(inputPath)) {
    console.error(`\x1b[31mError:\x1b[0m Input file not found: ${inputPath}`);
    process.exit(1);
  }

  if (!existsSync(outputDir)) {
    await mkdir(outputDir, { recursive: true });
  }

  const inputName = basename(inputPath, extname(inputPath));
  const outputName = output || `${inputName}-compressed`;
  const outputPath = join(outputDir, `${outputName}.mp3`);

  console.log(`\x1b[36m[cc0-audio]\x1b[0m Compressing with preset: ${preset}`);
  console.log(`\x1b[90mInput: ${inputPath}\x1b[0m`);

  let ffArgs: string[];

  if (preset === "custom") {
    if (!ffmpegArgs) {
      console.error("\x1b[31mError:\x1b[0m Custom preset requires --ffmpeg-args.");
      process.exit(1);
    }
    ffArgs = ["-y", "-i", inputPath, ...ffmpegArgs.split(" "), outputPath];
  } else {
    const presetArgs = COMPRESS_PRESETS[preset];
    if (!presetArgs) {
      console.error(`\x1b[31mError:\x1b[0m Unknown preset "${preset}". Valid: bgm, voice, custom`);
      process.exit(1);
    }
    ffArgs = ["-y", "-i", inputPath];
    if (duration) {
      ffArgs.push("-t", duration.toString());
    }
    ffArgs.push(...presetArgs, outputPath);
  }

  console.log(`\x1b[90mRunning: ffmpeg ${ffArgs.join(" ")}\x1b[0m`);

  try {
    await runCommand("ffmpeg", ffArgs);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    if (msg.includes("Failed to run ffmpeg") || msg.includes("ENOENT")) {
      console.error("\x1b[31mFFmpeg not found.\x1b[0m");
      console.error("Install it: https://ffmpeg.org/download.html");
      process.exit(1);
    }
    throw err;
  }

  console.log(`\x1b[32m[cc0-audio]\x1b[0m Compressed: ${outputPath}`);
  return outputPath;
}

async function cmdCheckUrls(args: string[]): Promise<void> {
  let baseUrl = "";

  let i = 0;
  while (i < args.length) {
    const arg = args[i];
    if (!arg.startsWith("-")) {
      baseUrl = arg;
    }
    i++;
  }

  if (!baseUrl) {
    console.error("\x1b[31mError:\x1b[0m No base URL provided.");
    console.error("Usage: cc0-audio check-urls https://example.com/audio/");
    process.exit(1);
  }

  // Normalize trailing slash
  if (!baseUrl.endsWith("/")) baseUrl += "/";

  console.log(`\x1b[36m[cc0-audio]\x1b[0m Checking audio URLs under: ${baseUrl}`);
  console.log("");

  // Fetch the base URL and look for .mp3 links
  const res = await fetch(baseUrl);
  if (!res.ok) {
    console.error(`\x1b[31mError:\x1b[0m Could not fetch ${baseUrl} — ${res.status}`);
    process.exit(1);
  }

  const html = await res.text();
  const mp3Pattern = /href=["']([^"']*\.mp3)["']/gi;
  const matches: string[] = [];
  let match: RegExpExecArray | null;

  while ((match = mp3Pattern.exec(html)) !== null) {
    matches.push(match[1]);
  }

  if (matches.length === 0) {
    console.log("\x1b[33mNo .mp3 files found in page listing.\x1b[0m");
    return;
  }

  console.log(`Found ${matches.length} .mp3 file(s). Checking reachability...\n`);

  let ok = 0;
  let fail = 0;

  for (const file of matches) {
    const fileUrl = file.startsWith("http") ? file : `${baseUrl}${file}`;
    try {
      const headRes = await fetch(fileUrl, { method: "HEAD" });
      const size = headRes.headers.get("content-length");
      const sizeStr = size ? `${(parseInt(size) / 1024).toFixed(0)} KB` : "unknown size";

      if (headRes.ok) {
        console.log(`  \x1b[32m${headRes.status}\x1b[0m  ${file}  \x1b[90m(${sizeStr})\x1b[0m`);
        ok++;
      } else {
        console.log(`  \x1b[31m${headRes.status}\x1b[0m  ${file}`);
        fail++;
      }
    } catch (err) {
      console.log(`  \x1b[31mERR\x1b[0m  ${file}  \x1b[90m(network error)\x1b[0m`);
      fail++;
    }
  }

  console.log(`\n\x1b[36m[cc0-audio]\x1b[0m Results: \x1b[32m${ok} OK\x1b[0m, \x1b[31m${fail} failed\x1b[0m`);
}

async function cmdBatch(args: string[]): Promise<void> {
  let manifestPath = "";
  let outputDir = process.cwd();
  let source = "freesound";
  let license = "cc0";
  let apiKeyFlag: string | undefined;

  let i = 0;
  while (i < args.length) {
    const arg = args[i];
    if (arg === "-d" || arg === "--dir") {
      outputDir = args[++i];
    } else if (arg === "--source") {
      source = args[++i];
    } else if (arg === "--license") {
      license = args[++i];
    } else if (arg === "--api-key") {
      apiKeyFlag = args[++i];
    } else if (!arg.startsWith("-")) {
      manifestPath = arg;
    }
    i++;
  }

  if (!manifestPath) {
    console.error("\x1b[31mError:\x1b[0m No manifest file provided.");
    console.error("Usage: cc0-audio batch manifest.json -d output/");
    process.exit(1);
  }

  const absPath = manifestPath.startsWith("/") || manifestPath.match(/^[A-Z]:/)
    ? manifestPath
    : join(process.cwd(), manifestPath);

  if (!existsSync(absPath)) {
    console.error(`\x1b[31mError:\x1b[0m Manifest not found: ${absPath}`);
    process.exit(1);
  }

  const apiKey = requireApiKey(apiKeyFlag);

  const manifest: BatchEntry[] = JSON.parse(await readFile(absPath, "utf-8"));
  console.log(`\x1b[36m[cc0-audio]\x1b[0m Batch processing ${manifest.length} entries...\n`);

  if (!existsSync(outputDir)) {
    await mkdir(outputDir, { recursive: true });
  }

  let success = 0;
  let errors = 0;

  for (let idx = 0; idx < manifest.length; idx++) {
    const entry = manifest[idx];
    const label = entry.output || `batch-${idx}`;
    console.log(`\x1b[36m[${idx + 1}/${manifest.length}]\x1b[0m ${entry.query}`);

    try {
      // Step 1: Search
      const licenseFilter = LICENSE_FILTERS[license] || "";
      const durationFilter = entry.duration ? ` duration:[0 TO ${entry.duration}]` : "";
      const filter = (licenseFilter + durationFilter).trim();

      const params = new URLSearchParams({
        query: entry.query,
        token: apiKey,
        fields: "id,name,duration,previews,license",
        page_size: "1",
      });
      if (filter) params.set("filter", filter);

      const searchUrl = `${FREESOUND_API}/search/text/?${params}`;
      const searchRes = await fetch(searchUrl);

      if (!searchRes.ok) {
        throw new Error(`Search failed: ${searchRes.status}`);
      }

      const data: FreesoundSearchResponse = await searchRes.json();
      if (data.results.length === 0) {
        console.log(`  \x1b[33mNo results, skipping.\x1b[0m\n`);
        errors++;
        continue;
      }

      const sound = data.results[0];
      console.log(`  \x1b[90mPicked: #${sound.id} — ${sound.name} (${formatDuration(sound.duration)})\x1b[0m`);

      // Step 2: Download preview
      const previewUrl = sound.previews?.["preview-hq-mp3"] || sound.previews?.["preview-lq-mp3"];
      if (!previewUrl) {
        console.log(`  \x1b[33mNo preview URL, skipping.\x1b[0m\n`);
        errors++;
        continue;
      }

      const rawPath = join(outputDir, `${label}-raw.mp3`);
      await downloadFile(previewUrl, rawPath);

      // Step 3: Compress
      const preset = entry.preset || "bgm";
      const presetArgs = COMPRESS_PRESETS[preset];

      if (presetArgs) {
        const finalPath = join(outputDir, `${label}.mp3`);
        const ffArgs = ["-y", "-i", rawPath];
        if (entry.duration) {
          ffArgs.push("-t", entry.duration.toString());
        }
        ffArgs.push(...presetArgs, finalPath);

        await runCommand("ffmpeg", ffArgs);

        // Clean up raw file
        const { unlink } = await import("fs/promises");
        await unlink(rawPath).catch(() => {});

        console.log(`  \x1b[32m+\x1b[0m ${finalPath}\n`);
      } else {
        // No compression, just rename
        const { rename } = await import("fs/promises");
        const finalPath = join(outputDir, `${label}.mp3`);
        await rename(rawPath, finalPath);
        console.log(`  \x1b[32m+\x1b[0m ${finalPath}\n`);
      }

      success++;
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      console.log(`  \x1b[31mx\x1b[0m Error: ${msg}\n`);
      errors++;
    }
  }

  console.log(`\x1b[36m[cc0-audio]\x1b[0m Batch complete: \x1b[32m${success} OK\x1b[0m, \x1b[31m${errors} failed\x1b[0m`);
}

// ---------------------------------------------------------------------------
// Argument parsing + main
// ---------------------------------------------------------------------------

function printHelp(): void {
  console.log(`
\x1b[36mCC0 Audio Sourcing CLI\x1b[0m — Search, download, and compress CC0 audio

\x1b[33mUsage:\x1b[0m
  cc0-audio search "dark fantasy ambient loop" [options]
  cc0-audio download <id-or-url> [options]
  cc0-audio compress <input> [options]
  cc0-audio check-urls <base-url>
  cc0-audio batch <manifest.json> [options]

\x1b[33mSubcommands:\x1b[0m
  search       Search Freesound.org for CC0 audio
  download     Download a sound by Freesound ID or direct URL
  compress     Compress audio with FFmpeg presets
  check-urls   Batch HEAD-check all .mp3 files under a URL
  batch        Search + download + compress from a JSON manifest

\x1b[33mSearch options:\x1b[0m
  --source     Source: freesound (default)
  --license    License filter: cc0 (default), cc-by, any
  --duration   Max duration in seconds
  --api-key    Freesound API key

\x1b[33mDownload options:\x1b[0m
  -o, --output    Output filename (without extension)
  -d, --dir       Output directory [default: cwd]
  --format        Force format: mp3, wav, ogg
  --api-key       Freesound API key

\x1b[33mCompress options:\x1b[0m
  --preset        Preset: bgm (default), voice, custom
  --duration      Trim to N seconds
  --ffmpeg-args   Custom FFmpeg args (requires --preset custom)
  -o, --output    Output filename (without extension)
  -d, --dir       Output directory [default: cwd]

\x1b[33mBatch options:\x1b[0m
  -d, --dir       Output directory [default: cwd]
  --source        Source: freesound (default)
  --license       License filter: cc0 (default), cc-by, any
  --api-key       Freesound API key

\x1b[33mCompress presets:\x1b[0m
  bgm     Mono, MP3 VBR q5, 44.1kHz (game background music)
  voice   Mono, MP3 VBR q6, 22.05kHz (voice / SFX)
  custom  Pass-through (provide --ffmpeg-args)

\x1b[33mBatch manifest format:\x1b[0m
  [
    { "query": "dark ambient loop", "preset": "bgm", "output": "ambient", "duration": 30 },
    { "query": "sword clash sfx", "preset": "voice", "output": "sword" }
  ]

\x1b[33mAPI Key:\x1b[0m
  Set FREESOUND_API_KEY via environment, .env file, or --api-key flag.
  Get a key at: https://freesound.org/apiv2/apply/

\x1b[33mExamples:\x1b[0m
  cc0-audio search "epic orchestral battle"
  cc0-audio search "rain ambience" --duration 60 --license cc0
  cc0-audio download 456789 -o rain-loop -d audio/
  cc0-audio download https://example.com/sound.mp3 -o mysound
  cc0-audio compress raw.wav --preset bgm --duration 30 -o bgm-loop
  cc0-audio check-urls https://cdn.example.com/audio/
  cc0-audio batch manifest.json -d output/
`);
}

async function main(): Promise<void> {
  const args = process.argv.slice(2);

  if (args.length === 0 || args[0] === "--help" || args[0] === "-h") {
    printHelp();
    process.exit(0);
  }

  const subcommand = args[0];
  const subArgs = args.slice(1);

  switch (subcommand) {
    case "search":
      await cmdSearch(subArgs);
      break;
    case "download":
      await cmdDownload(subArgs);
      break;
    case "compress":
      await cmdCompress(subArgs);
      break;
    case "check-urls":
      await cmdCheckUrls(subArgs);
      break;
    case "batch":
      await cmdBatch(subArgs);
      break;
    default:
      console.error(`\x1b[31mError:\x1b[0m Unknown subcommand "${subcommand}".`);
      console.error("Run cc0-audio --help for usage.");
      process.exit(1);
  }
}

main().catch((err) => {
  console.error("\x1b[31m[cc0-audio] Error:\x1b[0m", err.message);
  process.exit(1);
});
