#!/usr/bin/env bun
/**
 * Lyria - AI Music Generation CLI
 * Uses Google Lyria Realtime (models/lyria-realtime-exp) via WebSocket streaming
 *
 * Usage:
 *   lyria "mysterious dark fantasy ambient"
 *   lyria "upbeat electronic dance" --duration 60 --bpm 128
 *   lyria "calm piano melody" -o calm-piano --format wav
 */

import { GoogleGenAI } from "@google/genai";
import { writeFile, mkdir, readFile, unlink } from "fs/promises";
import { join, dirname } from "path";
import { existsSync, readFileSync } from "fs";
import { spawn } from "child_process";
import { fileURLToPath } from "url";
import { homedir } from "os";

// ---------------------------------------------------------------------------
// Environment / API key resolution
// Priority: --api-key flag > GEMINI_API_KEY env var > .env in cwd > .env next
// to this script > ~/.lyria/.env
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
loadEnvFile(join(homedir(), ".lyria", ".env"));

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MODEL = "models/lyria-realtime-exp";
const SAMPLE_RATE = 48000;
const CHANNELS = 2;
const BITS_PER_SAMPLE = 16;
const BLOCK_ALIGN = CHANNELS * (BITS_PER_SAMPLE / 8); // 4
const BYTE_RATE = SAMPLE_RATE * BLOCK_ALIGN; // 192000

const CONFIG_DIR = join(homedir(), ".lyria");
const COST_LOG_PATH = join(CONFIG_DIR, "costs.json");

const VALID_SCALES = [
  "C_MAJOR", "C_MINOR", "C_SHARP_MAJOR", "C_SHARP_MINOR",
  "D_MAJOR", "D_MINOR", "D_SHARP_MAJOR", "D_SHARP_MINOR",
  "E_MAJOR", "E_MINOR",
  "F_MAJOR", "F_MINOR", "F_SHARP_MAJOR", "F_SHARP_MINOR",
  "G_MAJOR", "G_MINOR", "G_SHARP_MAJOR", "G_SHARP_MINOR",
  "A_MAJOR", "A_MINOR", "A_SHARP_MAJOR", "A_SHARP_MINOR",
  "B_MAJOR", "B_MINOR",
] as const;

// Map user-friendly scale names to Lyria API Scale enum values.
// The API uses combined major/minor pairs per chromatic degree.
const SCALE_TO_API: Record<string, string> = {
  // C / Am
  "C_MAJOR": "C_MAJOR_A_MINOR", "A_MINOR": "C_MAJOR_A_MINOR",
  // Db / Bbm (C# = Db enharmonic)
  "C_SHARP_MAJOR": "D_FLAT_MAJOR_B_FLAT_MINOR", "C_SHARP_MINOR": "E_MAJOR_D_FLAT_MINOR",
  // D / Bm
  "D_MAJOR": "D_MAJOR_B_MINOR", "B_MINOR": "D_MAJOR_B_MINOR",
  // Eb / Cm (D# = Eb enharmonic)
  "D_SHARP_MAJOR": "E_FLAT_MAJOR_C_MINOR", "C_MINOR": "E_FLAT_MAJOR_C_MINOR",
  "D_SHARP_MINOR": "E_MAJOR_D_FLAT_MINOR",
  // E / C#m (Dbm)
  "E_MAJOR": "E_MAJOR_D_FLAT_MINOR", "E_MINOR": "G_MAJOR_E_MINOR",
  // F / Dm
  "F_MAJOR": "F_MAJOR_D_MINOR", "D_MINOR": "F_MAJOR_D_MINOR",
  // F# / Ebm (Gb = F# enharmonic)
  "F_SHARP_MAJOR": "G_FLAT_MAJOR_E_FLAT_MINOR", "F_SHARP_MINOR": "A_MAJOR_G_FLAT_MINOR",
  // G / Em
  "G_MAJOR": "G_MAJOR_E_MINOR", "G_MINOR": "B_FLAT_MAJOR_G_MINOR",
  "G_SHARP_MAJOR": "A_FLAT_MAJOR_F_MINOR", "G_SHARP_MINOR": "B_MAJOR_A_FLAT_MINOR",
  // Ab / Fm
  "F_MINOR": "A_FLAT_MAJOR_F_MINOR",
  // A / Gbm (F#m)
  "A_MAJOR": "A_MAJOR_G_FLAT_MINOR",
  // Bb / Gm (A# = Bb enharmonic)
  "A_SHARP_MAJOR": "B_FLAT_MAJOR_G_MINOR", "A_SHARP_MINOR": "D_FLAT_MAJOR_B_FLAT_MINOR",
  // B / Abm (G#m)
  "B_MAJOR": "B_MAJOR_A_FLAT_MINOR",
};

const VALID_MODES = ["QUALITY", "DIVERSITY", "VOCALIZATION"] as const;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Options {
  prompt: string;
  output: string;
  outputDir: string;
  duration: number;
  bpm: number | undefined;
  brightness: number | undefined;
  density: number | undefined;
  guidance: number;
  temperature: number;
  scale: string | undefined;
  mode: string;
  format: "mp3" | "wav";
  seed: number | undefined;
  noLoop: boolean;
  apiKey: string | undefined;
}

interface CostEntry {
  timestamp: string;
  model: string;
  duration: number;
  prompt: string;
  estimated_cost: number;
  output_file: string;
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

// ---------------------------------------------------------------------------
// WAV writer
// ---------------------------------------------------------------------------

function createWavBuffer(pcmData: Buffer): Buffer {
  const dataSize = pcmData.length;
  const header = Buffer.alloc(44);

  // RIFF header
  header.write("RIFF", 0);
  header.writeUInt32LE(36 + dataSize, 4); // chunk size
  header.write("WAVE", 8);

  // fmt sub-chunk
  header.write("fmt ", 12);
  header.writeUInt32LE(16, 16);           // sub-chunk size
  header.writeUInt16LE(1, 20);            // audio format (PCM)
  header.writeUInt16LE(CHANNELS, 22);     // channels
  header.writeUInt32LE(SAMPLE_RATE, 24);  // sample rate
  header.writeUInt32LE(BYTE_RATE, 28);    // byte rate
  header.writeUInt16LE(BLOCK_ALIGN, 30);  // block align
  header.writeUInt16LE(BITS_PER_SAMPLE, 32); // bits per sample

  // data sub-chunk
  header.write("data", 36);
  header.writeUInt32LE(dataSize, 40);

  return Buffer.concat([header, pcmData]);
}

// ---------------------------------------------------------------------------
// Cost tracking
// ---------------------------------------------------------------------------

async function logCost(entry: CostEntry): Promise<void> {
  if (!existsSync(CONFIG_DIR)) {
    await mkdir(CONFIG_DIR, { recursive: true });
  }

  let entries: CostEntry[] = [];
  if (existsSync(COST_LOG_PATH)) {
    try {
      const raw = await readFile(COST_LOG_PATH, "utf-8");
      entries = JSON.parse(raw);
    } catch {
      entries = [];
    }
  }

  entries.push(entry);
  await writeFile(COST_LOG_PATH, JSON.stringify(entries, null, 2));
}

function printCostSummary(): void {
  if (!existsSync(COST_LOG_PATH)) {
    console.log("\x1b[90mNo cost data found.\x1b[0m");
    return;
  }

  let entries: CostEntry[];
  try {
    entries = JSON.parse(readFileSync(COST_LOG_PATH, "utf-8"));
  } catch {
    console.log("\x1b[31mError reading cost log.\x1b[0m");
    return;
  }

  if (entries.length === 0) {
    console.log("\x1b[90mNo generations logged yet.\x1b[0m");
    return;
  }

  let totalCost = 0;
  let totalDuration = 0;

  for (const e of entries) {
    totalCost += e.estimated_cost;
    totalDuration += e.duration;
  }

  console.log(`\x1b[35m[lyria]\x1b[0m Cost Summary`);
  console.log(`\x1b[90m${"─".repeat(50)}\x1b[0m`);
  console.log(`  Total generations: ${entries.length}`);
  console.log(`  Total duration:    ${totalDuration}s`);
  console.log(`  Total cost:        \x1b[33m$${totalCost.toFixed(4)}\x1b[0m`);
  console.log(`\x1b[90m${"─".repeat(50)}\x1b[0m`);
  console.log(`\x1b[90mNote: Lyria is free during preview (cost = $0.00)\x1b[0m`);
  console.log(`\x1b[90mLog: ${COST_LOG_PATH}\x1b[0m`);
}

// ---------------------------------------------------------------------------
// Argument parsing
// ---------------------------------------------------------------------------

function parseArgs(): Options | "costs" {
  const args = process.argv.slice(2);

  if (args.length === 0 || args[0] === "--help" || args[0] === "-h") {
    console.log(`
\x1b[35mLyria\x1b[0m - AI Music Generation CLI
Model: Lyria Realtime (${MODEL})

\x1b[33mUsage:\x1b[0m
  lyria "mysterious dark fantasy ambient"
  lyria "upbeat electronic dance" --duration 60 --bpm 128
  lyria "calm piano melody" -o calm-piano --format wav

\x1b[33mOptions:\x1b[0m
  -o, --output      Output filename (without extension) [default: lyria-{timestamp}]
  -d, --dir         Output directory [default: current directory]
  --duration        Duration in seconds [default: 30]
  --bpm             Beats per minute (60-200) [default: auto]
  --brightness      Tonal character (0.0-1.0) [default: auto]
  --density         Note density (0.0-1.0) [default: auto]
  --guidance        Prompt adherence (0.0-6.0) [default: 4.0]
  --temperature     Randomness [default: 1.1]
  --scale           Musical key: C_MAJOR, A_MINOR, etc. [default: auto]
  --mode            QUALITY, DIVERSITY, or VOCALIZATION [default: QUALITY]
  --format          Output format: mp3 or wav [default: mp3]
  --seed            Reproducibility seed [default: random]
  --no-loop         Don't attempt loop-point detection
  --api-key         Gemini API key (overrides env/file)
  --costs           Show cost summary from generation history
  -h, --help        Show this help

\x1b[33mScales:\x1b[0m
  C_MAJOR, C_MINOR, D_MAJOR, D_MINOR, E_MAJOR, E_MINOR,
  F_MAJOR, F_MINOR, G_MAJOR, G_MINOR, A_MAJOR, A_MINOR,
  B_MAJOR, B_MINOR (and sharps: C_SHARP_MAJOR, etc.)

\x1b[33mModes:\x1b[0m
  QUALITY       Best quality output (default)
  DIVERSITY     More varied/experimental output
  VOCALIZATION  Include vocal-like elements

\x1b[33mExamples:\x1b[0m
  lyria "mysterious dark fantasy ambient"
  lyria "upbeat electronic dance" --duration 60 --bpm 128
  lyria "epic orchestral battle theme" --mode QUALITY --guidance 5.0
  lyria "lofi hip hop beats" --bpm 85 --brightness 0.3 -o lofi
  lyria "jazz piano trio" --scale D_MINOR --density 0.6

\x1b[33mCost Tracking:\x1b[0m
  lyria --costs     Show usage history (free during preview)

\x1b[33mAPI Key:\x1b[0m
  Set GEMINI_API_KEY in your environment, a .env file, or pass --api-key.
  Get a key at: https://aistudio.google.com/apikey
`);
    process.exit(0);
  }

  if (args[0] === "--costs") {
    return "costs";
  }

  const options: Options = {
    prompt: "",
    output: `lyria-${Date.now()}`,
    outputDir: process.cwd(),
    duration: 30,
    bpm: undefined,
    brightness: undefined,
    density: undefined,
    guidance: 4.0,
    temperature: 1.1,
    scale: undefined,
    mode: "QUALITY",
    format: "mp3",
    seed: undefined,
    noLoop: false,
    apiKey: undefined,
  };

  let i = 0;
  while (i < args.length) {
    const arg = args[i];

    if (arg === "-o" || arg === "--output") {
      options.output = args[++i];
    } else if (arg === "-d" || arg === "--dir") {
      options.outputDir = args[++i];
    } else if (arg === "--duration") {
      const val = parseInt(args[++i], 10);
      if (isNaN(val) || val < 1) {
        console.error(`\x1b[31mError:\x1b[0m Invalid duration. Must be a positive integer.`);
        process.exit(1);
      }
      options.duration = val;
    } else if (arg === "--bpm") {
      const val = parseInt(args[++i], 10);
      if (isNaN(val) || val < 60 || val > 200) {
        console.error(`\x1b[31mError:\x1b[0m Invalid BPM "${args[i]}". Must be 60-200.`);
        process.exit(1);
      }
      options.bpm = val;
    } else if (arg === "--brightness") {
      const val = parseFloat(args[++i]);
      if (isNaN(val) || val < 0 || val > 1) {
        console.error(`\x1b[31mError:\x1b[0m Invalid brightness "${args[i]}". Must be 0.0-1.0.`);
        process.exit(1);
      }
      options.brightness = val;
    } else if (arg === "--density") {
      const val = parseFloat(args[++i]);
      if (isNaN(val) || val < 0 || val > 1) {
        console.error(`\x1b[31mError:\x1b[0m Invalid density "${args[i]}". Must be 0.0-1.0.`);
        process.exit(1);
      }
      options.density = val;
    } else if (arg === "--guidance") {
      const val = parseFloat(args[++i]);
      if (isNaN(val) || val < 0 || val > 6) {
        console.error(`\x1b[31mError:\x1b[0m Invalid guidance "${args[i]}". Must be 0.0-6.0.`);
        process.exit(1);
      }
      options.guidance = val;
    } else if (arg === "--temperature") {
      const val = parseFloat(args[++i]);
      if (isNaN(val)) {
        console.error(`\x1b[31mError:\x1b[0m Invalid temperature "${args[i]}".`);
        process.exit(1);
      }
      options.temperature = val;
    } else if (arg === "--scale") {
      const val = args[++i].toUpperCase();
      if (!VALID_SCALES.includes(val as (typeof VALID_SCALES)[number])) {
        console.error(`\x1b[31mError:\x1b[0m Invalid scale "${val}".`);
        console.error(`Valid: ${VALID_SCALES.join(", ")}`);
        process.exit(1);
      }
      options.scale = val;
    } else if (arg === "--mode") {
      const val = args[++i].toUpperCase();
      if (!VALID_MODES.includes(val as (typeof VALID_MODES)[number])) {
        console.error(`\x1b[31mError:\x1b[0m Invalid mode "${val}". Valid: ${VALID_MODES.join(", ")}`);
        process.exit(1);
      }
      options.mode = val;
    } else if (arg === "--format") {
      const val = args[++i].toLowerCase();
      if (val !== "mp3" && val !== "wav") {
        console.error(`\x1b[31mError:\x1b[0m Invalid format "${val}". Valid: mp3, wav`);
        process.exit(1);
      }
      options.format = val as "mp3" | "wav";
    } else if (arg === "--seed") {
      const val = parseInt(args[++i], 10);
      if (isNaN(val)) {
        console.error(`\x1b[31mError:\x1b[0m Invalid seed "${args[i]}". Must be an integer.`);
        process.exit(1);
      }
      options.seed = val;
    } else if (arg === "--no-loop") {
      options.noLoop = true;
    } else if (arg === "--api-key") {
      options.apiKey = args[++i];
    } else if (!arg.startsWith("-")) {
      options.prompt = arg;
    }
    i++;
  }

  if (!options.prompt) {
    console.error("\x1b[31mError:\x1b[0m No prompt provided");
    process.exit(1);
  }

  return options;
}

// ---------------------------------------------------------------------------
// Music generation
// ---------------------------------------------------------------------------

async function generateMusic(options: Options): Promise<string> {
  const apiKey = options.apiKey || process.env.GEMINI_API_KEY;

  if (!apiKey) {
    console.error("\x1b[31mError:\x1b[0m GEMINI_API_KEY is required.");
    console.error("");
    console.error("Set it one of these ways:");
    console.error("  1. Export:    export GEMINI_API_KEY=your_key");
    console.error("  2. .env:     Create .env with GEMINI_API_KEY=your_key");
    console.error("  3. Flag:     lyria \"prompt\" --api-key your_key");
    console.error("  4. Config:   mkdir -p ~/.lyria && echo 'GEMINI_API_KEY=your_key' > ~/.lyria/.env");
    console.error("");
    console.error("Get a key at: https://aistudio.google.com/apikey");
    process.exit(1);
  }

  // Print generation info
  console.log(`\x1b[35m[lyria]\x1b[0m Generating music...`);
  console.log(`\x1b[90mModel: Lyria Realtime\x1b[0m`);
  console.log(`\x1b[90mPrompt: ${options.prompt}\x1b[0m`);
  console.log(`\x1b[90mDuration: ${options.duration}s | Mode: ${options.mode} | Format: ${options.format}\x1b[0m`);

  const configParts: string[] = [];
  if (options.bpm !== undefined) configParts.push(`BPM: ${options.bpm}`);
  if (options.brightness !== undefined) configParts.push(`Brightness: ${options.brightness}`);
  if (options.density !== undefined) configParts.push(`Density: ${options.density}`);
  if (options.scale !== undefined) configParts.push(`Scale: ${options.scale}`);
  configParts.push(`Guidance: ${options.guidance}`);
  configParts.push(`Temperature: ${options.temperature}`);
  if (options.seed !== undefined) configParts.push(`Seed: ${options.seed}`);
  console.log(`\x1b[90m${configParts.join(" | ")}\x1b[0m`);
  console.log("");

  // Connect to Lyria WebSocket
  console.log(`  \x1b[90mConnecting to Lyria WebSocket...\x1b[0m`);
  const client = new GoogleGenAI({ apiKey, httpOptions: { apiVersion: "v1alpha" } });

  const targetBytes = options.duration * BYTE_RATE;
  const pcmChunks: Buffer[] = [];
  let totalBytes = 0;
  const startTime = Date.now();
  let dataReceived = false;
  let doneResolve: () => void;
  const donePromise = new Promise<void>((resolve) => { doneResolve = resolve; });
  let setupResolve: () => void;
  const setupPromise = new Promise<void>((resolve) => { setupResolve = resolve; });

  const session = await (client as any).live.music.connect({
    model: MODEL,
    callbacks: {
      onmessage: (msg: any) => {
        // Wait for setupComplete before proceeding
        if (msg.setupComplete) {
          console.log(`  \x1b[90mSetup complete, ready to generate.\x1b[0m`);
          setupResolve();
          return;
        }

        // Audio data arrives in serverContent.audioChunks
        if (msg.serverContent?.audioChunks) {
          for (const chunk of msg.serverContent.audioChunks) {
            if (chunk.data) {
              dataReceived = true;
              const buffer = Buffer.from(chunk.data, "base64");
              pcmChunks.push(buffer);
              totalBytes += buffer.length;

              // Progress indicator
              const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
              const progress = Math.min(100, (totalBytes / targetBytes) * 100).toFixed(0);
              process.stdout.write(`\r  \x1b[90mReceiving PCM data... ${progress}% (${elapsed}s elapsed)\x1b[0m`);

              if (totalBytes >= targetBytes) {
                doneResolve();
              }
            }
          }
        }

        // Log any filtered prompts
        if (msg.serverContent?.filteredPrompt) {
          console.error(`\n\x1b[33m  Warning: prompt was filtered.\x1b[0m`);
        }
      },
      onerror: (e: any) => {
        console.error(`\n\x1b[31m  WebSocket error:\x1b[0m`, e.message || e);
        doneResolve();
      },
      onclose: () => {
        // Only resolve if we haven't started receiving data or if we're done
        if (!dataReceived || totalBytes >= targetBytes) {
          doneResolve();
        } else {
          console.error(`\n\x1b[33m  Connection closed early at ${totalBytes}/${targetBytes} bytes.\x1b[0m`);
          doneResolve();
        }
      },
    },
  });

  // Wait for setup to complete before sending commands
  await setupPromise;

  // Set weighted prompts
  console.log(`  \x1b[90mSetting prompts...\x1b[0m`);
  await session.setWeightedPrompts({ weightedPrompts: [{ text: options.prompt, weight: 1.0 }] });

  // Build generation config
  const genConfig: Record<string, any> = {
    guidance: options.guidance,
    temperature: options.temperature,
    musicGenerationMode: options.mode,
  };
  if (options.bpm !== undefined) genConfig.bpm = options.bpm;
  if (options.brightness !== undefined) genConfig.brightness = options.brightness;
  if (options.density !== undefined) genConfig.density = options.density;
  if (options.scale !== undefined) genConfig.scale = SCALE_TO_API[options.scale] || options.scale;
  if (options.seed !== undefined) genConfig.seed = options.seed;
  if (options.noLoop) genConfig.loopEnabled = false;

  console.log(`  \x1b[90mSetting generation config...\x1b[0m`);
  await session.setMusicGenerationConfig({ musicGenerationConfig: genConfig });

  // Start playback and collect PCM chunks via callback
  console.log(`  \x1b[90mStarting generation...\x1b[0m`);
  session.play();

  // Wait until we've received enough data or the connection closes
  await donePromise;

  process.stdout.write("\n");
  console.log(`  \x1b[90mStopping session...\x1b[0m`);
  try { session.stop(); } catch (_) {}
  try { session.close(); } catch (_) {}

  // Truncate to exact duration
  const pcmData = Buffer.concat(pcmChunks);
  const trimmedPcm = pcmData.subarray(0, targetBytes);

  const elapsedTotal = ((Date.now() - startTime) / 1000).toFixed(1);
  console.log(`  \x1b[90mReceived ${(trimmedPcm.length / 1024).toFixed(0)} KB of PCM data in ${elapsedTotal}s\x1b[0m`);

  // Ensure output directory exists
  if (!existsSync(options.outputDir)) {
    await mkdir(options.outputDir, { recursive: true });
  }

  // Write raw PCM to disk (used for both WAV and MP3 paths)
  const rawPcmPath = join(options.outputDir, `${options.output}.raw`);
  await writeFile(rawPcmPath, trimmedPcm);

  let finalPath: string;

  if (options.format === "mp3") {
    // Convert raw PCM directly to MP3 (bypass WAV container issues)
    const mp3Path = join(options.outputDir, `${options.output}.mp3`);
    console.log(`  \x1b[90mConverting to MP3...\x1b[0m`);

    try {
      await runCommand("ffmpeg", [
        "-y",
        "-f", "s16le",
        "-ar", String(SAMPLE_RATE),
        "-ac", String(CHANNELS),
        "-i", rawPcmPath,
        "-c:a", "libmp3lame",
        "-ac", "1",
        "-q:a", "5",
        "-ar", "44100",
        mp3Path,
      ]);

      await unlink(rawPcmPath);
      console.log(`  \x1b[32m+\x1b[0m MP3 written: ${mp3Path}`);
      finalPath = mp3Path;
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes("Failed to run ffmpeg") || msg.includes("ENOENT")) {
        console.error(`\x1b[33m  FFmpeg not found — saving as WAV instead.\x1b[0m`);
        console.error(`  Install FFmpeg for MP3 conversion: https://ffmpeg.org/download.html`);
      } else {
        console.error(`\x1b[33m  FFmpeg conversion failed — saving as WAV instead.\x1b[0m`);
        console.error(`  \x1b[90m${msg}\x1b[0m`);
      }
      // Fall back to WAV
      const wavPath = join(options.outputDir, `${options.output}.wav`);
      const wavBuffer = createWavBuffer(trimmedPcm);
      await writeFile(wavPath, wavBuffer);
      await unlink(rawPcmPath).catch(() => {});
      console.log(`  \x1b[32m+\x1b[0m WAV written: ${wavPath}`);
      finalPath = wavPath;
    }
  } else {
    // Write WAV file
    const wavPath = join(options.outputDir, `${options.output}.wav`);
    const wavBuffer = createWavBuffer(trimmedPcm);
    await writeFile(wavPath, wavBuffer);
    await unlink(rawPcmPath).catch(() => {});
    console.log(`  \x1b[32m+\x1b[0m WAV written: ${wavPath}`);
    finalPath = wavPath;
  }

  // Log cost
  const entry: CostEntry = {
    timestamp: new Date().toISOString(),
    model: MODEL,
    duration: options.duration,
    prompt: options.prompt,
    estimated_cost: 0, // Free during preview
    output_file: finalPath,
  };

  await logCost(entry).catch(() => {
    // Non-fatal
  });

  return finalPath;
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

const parsed = parseArgs();

if (parsed === "costs") {
  printCostSummary();
  process.exit(0);
}

const options = parsed;

generateMusic(options)
  .then((file) => {
    console.log(`\n\x1b[32m[lyria]\x1b[0m Generation complete:`);
    console.log(`  \x1b[32m+\x1b[0m ${file}`);
    console.log(`\x1b[90mCost: $0.00 (free during preview)\x1b[0m`);
  })
  .catch((err) => {
    console.error("\x1b[31m[lyria] Error:\x1b[0m", err.message);
    process.exit(1);
  });
