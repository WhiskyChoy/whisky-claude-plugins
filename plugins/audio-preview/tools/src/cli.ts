#!/usr/bin/env bun
/**
 * Audio Preview — Zero-dependency local web server for comparing audio files.
 * Opens a browser UI where the user can play, compare, and pick audio files.
 *
 * Usage:
 *   audio-preview [directory]              # Serve audio files from directory
 *   audio-preview [file1] [file2] ...      # Serve specific files
 *   audio-preview --port 9090 ./audio      # Custom port
 */

import { readdirSync, statSync, readFileSync, existsSync } from "fs";
import { join, basename, extname, resolve } from "path";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const AUDIO_EXTS = new Set([".mp3", ".ogg", ".wav", ".flac", ".m4a", ".aac", ".webm"]);
const MIME_TYPES: Record<string, string> = {
  ".mp3": "audio/mpeg",
  ".ogg": "audio/ogg",
  ".wav": "audio/wav",
  ".flac": "audio/flac",
  ".m4a": "audio/mp4",
  ".aac": "audio/aac",
  ".webm": "audio/webm",
};
const DEFAULT_PORT = 8111;

// ---------------------------------------------------------------------------
// Collect audio files
// ---------------------------------------------------------------------------

interface AudioFile {
  name: string;
  path: string;
  size: number;
  ext: string;
}

function collectFiles(inputs: string[]): AudioFile[] {
  const files: AudioFile[] = [];

  for (const input of inputs) {
    const abs = resolve(input);
    if (!existsSync(abs)) {
      console.error(`\x1b[33mWarning:\x1b[0m Not found: ${abs}`);
      continue;
    }

    const stat = statSync(abs);
    if (stat.isDirectory()) {
      // Scan directory for audio files
      for (const entry of readdirSync(abs)) {
        const ext = extname(entry).toLowerCase();
        if (!AUDIO_EXTS.has(ext)) continue;
        const filePath = join(abs, entry);
        const fileStat = statSync(filePath);
        files.push({ name: entry, path: filePath, size: fileStat.size, ext });
      }
      // Also scan one level of subdirectories
      for (const sub of readdirSync(abs)) {
        const subPath = join(abs, sub);
        if (!statSync(subPath).isDirectory()) continue;
        for (const entry of readdirSync(subPath)) {
          const ext = extname(entry).toLowerCase();
          if (!AUDIO_EXTS.has(ext)) continue;
          const filePath = join(subPath, entry);
          const fileStat = statSync(filePath);
          files.push({ name: `${sub}/${entry}`, path: filePath, size: fileStat.size, ext });
        }
      }
    } else if (stat.isFile()) {
      const ext = extname(abs).toLowerCase();
      if (AUDIO_EXTS.has(ext)) {
        files.push({ name: basename(abs), path: abs, size: stat.size, ext });
      } else {
        console.error(`\x1b[33mWarning:\x1b[0m Not an audio file: ${abs}`);
      }
    }
  }

  return files;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// ---------------------------------------------------------------------------
// HTML UI
// ---------------------------------------------------------------------------

function generateHTML(files: AudioFile[]): string {
  const fileRows = files.map((f, i) => `
    <div class="track${i === 0 ? " active" : ""}" data-idx="${i}">
      <div class="track-info">
        <span class="track-num">${i + 1}</span>
        <span class="track-name">${f.name}</span>
        <span class="track-size">${formatSize(f.size)}</span>
      </div>
      <div class="track-controls">
        <audio id="audio-${i}" preload="metadata">
          <source src="/file/${i}" type="${MIME_TYPES[f.ext] || "audio/mpeg"}">
        </audio>
        <button class="btn play-btn" onclick="togglePlay(${i})">Play</button>
        <button class="btn pick-btn" onclick="pickTrack(${i})">Pick</button>
      </div>
      <div class="waveform">
        <div class="progress" id="progress-${i}"></div>
      </div>
    </div>
  `).join("\n");

  return `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Audio Preview</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #1a1a2e; color: #e0e0e0; padding: 20px; max-width: 800px; margin: 0 auto; }
  h1 { font-size: 1.4em; margin-bottom: 4px; color: #7fdbca; }
  .subtitle { color: #666; font-size: 0.85em; margin-bottom: 20px; }
  .track { background: #16213e; border: 1px solid #0f3460; border-radius: 8px; padding: 12px 16px; margin-bottom: 10px; cursor: pointer; transition: all 0.15s; }
  .track:hover { border-color: #e94560; }
  .track.active { border-color: #7fdbca; background: #1a2a4a; }
  .track.playing { border-color: #e94560; box-shadow: 0 0 12px rgba(233,69,96,0.3); }
  .track.picked { border-color: #ffd700; background: #2a2a1a; box-shadow: 0 0 12px rgba(255,215,0,0.3); }
  .track-info { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
  .track-num { background: #0f3460; color: #7fdbca; width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 0.75em; font-weight: bold; flex-shrink: 0; }
  .track-name { flex: 1; font-weight: 500; word-break: break-all; }
  .track-size { color: #666; font-size: 0.8em; flex-shrink: 0; }
  .track-controls { display: flex; gap: 8px; margin-bottom: 6px; }
  .btn { padding: 5px 16px; border: none; border-radius: 4px; cursor: pointer; font-size: 0.85em; font-weight: 500; transition: all 0.1s; }
  .play-btn { background: #0f3460; color: #7fdbca; }
  .play-btn:hover { background: #1a4a7a; }
  .play-btn.active { background: #e94560; color: white; }
  .pick-btn { background: #2a2a1a; color: #ffd700; border: 1px solid #554400; }
  .pick-btn:hover { background: #3a3a2a; }
  .waveform { height: 4px; background: #0f3460; border-radius: 2px; overflow: hidden; }
  .progress { height: 100%; width: 0%; background: #e94560; transition: width 0.1s linear; }
  .result { margin-top: 20px; padding: 16px; background: #1a3a1a; border: 1px solid #2a5a2a; border-radius: 8px; display: none; }
  .result.show { display: block; }
  .result h3 { color: #7fdbca; margin-bottom: 8px; }
  .result code { background: #0f3460; padding: 2px 8px; border-radius: 3px; font-size: 0.9em; }
  .stop-all { background: #333; color: #999; margin-top: 16px; width: 100%; padding: 8px; }
  .stop-all:hover { background: #444; color: #ccc; }
</style>
</head>
<body>
<h1>Audio Preview</h1>
<p class="subtitle">${files.length} file(s) — click Play to listen, Pick to select</p>

${fileRows}

<button class="btn stop-all" onclick="stopAll()">Stop All</button>

<div class="result" id="result">
  <h3>Selected:</h3>
  <p><code id="result-name"></code></p>
</div>

<script>
let currentPlaying = -1;
const audios = [];
for (let i = 0; i < ${files.length}; i++) {
  const a = document.getElementById('audio-' + i);
  audios.push(a);
  a.addEventListener('timeupdate', () => {
    const p = document.getElementById('progress-' + i);
    if (a.duration) p.style.width = (a.currentTime / a.duration * 100) + '%';
  });
  a.addEventListener('ended', () => {
    document.querySelector('[data-idx="' + i + '"]').classList.remove('playing');
    document.querySelector('[data-idx="' + i + '"] .play-btn').textContent = 'Play';
    document.querySelector('[data-idx="' + i + '"] .play-btn').classList.remove('active');
    currentPlaying = -1;
  });
}

function stopAll() {
  audios.forEach((a, i) => {
    a.pause(); a.currentTime = 0;
    document.querySelector('[data-idx="' + i + '"]').classList.remove('playing');
    document.querySelector('[data-idx="' + i + '"] .play-btn').textContent = 'Play';
    document.querySelector('[data-idx="' + i + '"] .play-btn').classList.remove('active');
    document.getElementById('progress-' + i).style.width = '0%';
  });
  currentPlaying = -1;
}

function togglePlay(idx) {
  const a = audios[idx];
  if (currentPlaying === idx) {
    a.pause();
    document.querySelector('[data-idx="' + idx + '"]').classList.remove('playing');
    document.querySelector('[data-idx="' + idx + '"] .play-btn').textContent = 'Play';
    document.querySelector('[data-idx="' + idx + '"] .play-btn').classList.remove('active');
    currentPlaying = -1;
  } else {
    stopAll();
    a.play();
    document.querySelector('[data-idx="' + idx + '"]').classList.add('playing');
    document.querySelector('[data-idx="' + idx + '"] .play-btn').textContent = 'Pause';
    document.querySelector('[data-idx="' + idx + '"] .play-btn').classList.add('active');
    currentPlaying = idx;
  }
}

function pickTrack(idx) {
  document.querySelectorAll('.track').forEach(t => t.classList.remove('picked'));
  document.querySelector('[data-idx="' + idx + '"]').classList.add('picked');
  const name = document.querySelector('[data-idx="' + idx + '"] .track-name').textContent;
  document.getElementById('result-name').textContent = name;
  document.getElementById('result').classList.add('show');
  // Notify server
  fetch('/pick/' + idx, { method: 'POST' });
}
</script>
</body>
</html>`;
}

// ---------------------------------------------------------------------------
// Parse args
// ---------------------------------------------------------------------------

function parseArgs(): { inputs: string[]; port: number } {
  const args = process.argv.slice(2);

  if (args.length === 0 || args[0] === "--help" || args[0] === "-h") {
    console.log(`
\x1b[36mAudio Preview\x1b[0m — Compare and pick audio files in a browser UI

\x1b[33mUsage:\x1b[0m
  audio-preview [directory]              Serve all audio files in a directory
  audio-preview [file1] [file2] ...      Serve specific files
  audio-preview -d dir1 -d dir2          Serve from multiple directories

\x1b[33mOptions:\x1b[0m
  -p, --port    Port number [default: ${DEFAULT_PORT}]
  -h, --help    Show this help

\x1b[33mExamples:\x1b[0m
  audio-preview ./audio/candidates/
  audio-preview track1.mp3 track2.mp3 track3.ogg
  audio-preview ./classic/ ./cataclysm/ --port 9000

\x1b[33mSupported formats:\x1b[0m
  mp3, ogg, wav, flac, m4a, aac, webm
`);
    process.exit(0);
  }

  let port = DEFAULT_PORT;
  const inputs: string[] = [];

  let i = 0;
  while (i < args.length) {
    const arg = args[i];
    if (arg === "-p" || arg === "--port") {
      port = parseInt(args[++i], 10);
    } else if (arg === "-d" || arg === "--dir") {
      inputs.push(args[++i]);
    } else if (!arg.startsWith("-")) {
      inputs.push(arg);
    }
    i++;
  }

  if (inputs.length === 0) inputs.push(".");

  return { inputs, port };
}

// ---------------------------------------------------------------------------
// Server
// ---------------------------------------------------------------------------

const { inputs, port } = parseArgs();
const files = collectFiles(inputs);

if (files.length === 0) {
  console.error("\x1b[31mError:\x1b[0m No audio files found.");
  process.exit(1);
}

console.log(`\x1b[36m[audio-preview]\x1b[0m Found ${files.length} audio file(s):`);
files.forEach((f, i) => console.log(`  \x1b[33m${i + 1}\x1b[0m  ${f.name}  \x1b[90m(${formatSize(f.size)})\x1b[0m`));
console.log("");

let pickedFile: string | null = null;

const server = Bun.serve({
  port,
  fetch(req) {
    const url = new URL(req.url);

    if (url.pathname === "/" || url.pathname === "/index.html") {
      return new Response(generateHTML(files), {
        headers: { "Content-Type": "text/html; charset=utf-8" },
      });
    }

    // Serve audio file by index
    const fileMatch = url.pathname.match(/^\/file\/(\d+)$/);
    if (fileMatch) {
      const idx = parseInt(fileMatch[1], 10);
      if (idx >= 0 && idx < files.length) {
        const f = files[idx];
        const data = readFileSync(f.path);
        return new Response(data, {
          headers: {
            "Content-Type": MIME_TYPES[f.ext] || "application/octet-stream",
            "Content-Length": String(data.length),
            "Accept-Ranges": "bytes",
          },
        });
      }
    }

    // Pick endpoint
    const pickMatch = url.pathname.match(/^\/pick\/(\d+)$/);
    if (pickMatch && req.method === "POST") {
      const idx = parseInt(pickMatch[1], 10);
      if (idx >= 0 && idx < files.length) {
        pickedFile = files[idx].path;
        console.log(`\n\x1b[32m[audio-preview]\x1b[0m Picked: \x1b[33m${files[idx].name}\x1b[0m`);
        console.log(`\x1b[90m  Path: ${pickedFile}\x1b[0m`);
      }
      return new Response("ok");
    }

    return new Response("Not found", { status: 404 });
  },
});

const url = `http://localhost:${server.port}`;
console.log(`\x1b[32m[audio-preview]\x1b[0m Server running at \x1b[36m${url}\x1b[0m`);
console.log(`\x1b[90mPress Ctrl+C to stop.\x1b[0m\n`);

// Try to open browser
try {
  const { platform } = process;
  const cmd = platform === "win32" ? "start" : platform === "darwin" ? "open" : "xdg-open";
  Bun.spawn([cmd, url], { stdout: "ignore", stderr: "ignore" });
} catch {
  // Non-fatal — user can open manually
}
