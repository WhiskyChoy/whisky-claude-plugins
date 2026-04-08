#!/usr/bin/env python3
"""
Generate an HTML page with audio clips for each speaker to help users
identify who is who.

Usage:
    python identify_speakers.py \
        --transcript unified/transfer/2026-03-06_140525.json \
        --audio unified/audio/2026-03-06_140525.mp3 \
        --output unified/transfer/2026-03-06_140525_identify.html \
        [--speakers-md unified/transfer/2026-03-06_140525_speakers.md] \
        [--clips-dir unified/transfer/_clips] \
        [--open]

The generated HTML page:
  - Shows each speaker as a card with audio clips, stats, and role clues
  - Has editable text fields for speaker names (pre-filled with AI predictions)
  - "Save" button downloads a speaker-map.json file
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import webbrowser
from collections import defaultdict
from pathlib import Path


def load_transcript(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_speakers_md(path):
    """Parse _speakers.md to extract role clues and predictions per speaker."""
    if not path or not Path(path).exists():
        return {}

    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    speakers = {}
    # Split by ## SPEAKER_XX headers
    sections = re.split(r"^## (SPEAKER_\d+)", text, flags=re.MULTILINE)
    for i in range(1, len(sections), 2):
        spk_id = sections[i].strip()
        body = sections[i + 1] if i + 1 < len(sections) else ""

        # Extract predicted name from "→ XXX" pattern
        name_match = re.search(r"→\s*(.+?)(?:\n|$)", body)
        predicted = name_match.group(1).strip() if name_match else ""

        # Extract role clues section
        clues = []
        clue_match = re.search(
            r"\*\*角色线索\*\*[：:]\s*\n((?:\s+-\s+.+\n)*)", body
        )
        if clue_match:
            clues = [
                line.strip().lstrip("- ")
                for line in clue_match.group(1).strip().split("\n")
                if line.strip()
            ]

        speakers[spk_id] = {"predicted": predicted, "clues": clues}

    return speakers


def select_clips(segments, speaker_id, max_clips=5):
    """Select representative clips for a speaker: first, longest, and spread across time."""
    spk_segs = [s for s in segments if s["speaker"] == speaker_id]
    if not spk_segs:
        return []

    selected = []
    labels = []

    # 1. First utterance
    first = spk_segs[0]
    selected.append(first)
    labels.append("首次发言")

    # 2. Longest utterance (by text length)
    longest = max(spk_segs, key=lambda s: len(s.get("text", "")))
    if longest not in selected:
        selected.append(longest)
        labels.append("最长发言")

    # 3. Spread across time — divide into quartiles and pick one from each
    if len(spk_segs) > 4:
        quarter = len(spk_segs) // 4
        for q, label in [
            (1, "中前段"),
            (2, "中段"),
            (3, "后段"),
        ]:
            candidate = spk_segs[q * quarter]
            if candidate not in selected and len(selected) < max_clips:
                selected.append(candidate)
                labels.append(label)

    return list(zip(selected, labels))


def cut_clip(audio_path, start, end, output_path, padding=0.5):
    """Use ffmpeg to cut an audio clip."""
    start_padded = max(0, start - padding)
    duration = (end - start) + 2 * padding

    cmd = [
        "ffmpeg", "-y", "-i", str(audio_path),
        "-ss", str(start_padded),
        "-t", str(duration),
        "-ar", "16000", "-ac", "1",
        "-q:a", "5",
        str(output_path),
    ]
    subprocess.run(cmd, capture_output=True, check=True)


def format_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _build_merge_options(current_id, all_speakers):
    """Build <option> tags for 'merge into SPEAKER_XX' dropdown."""
    opts = []
    for s in all_speakers:
        if s["id"] != current_id:
            opts.append(f'<option value="合并到 {s["id"]}">合并到 {s["id"]}</option>')
    return "".join(opts)


def generate_html(speakers_data, clips_dir_rel):
    """Generate the HTML page content."""
    cards_html = []

    for spk in speakers_data:
        clips_html = ""
        for clip in spk["clips"]:
            clips_html += f"""
            <div class="clip">
                <span class="clip-label">{clip["label"]} [{clip["time"]}]</span>
                <audio controls preload="none" src="{clip["path"]}"></audio>
                <span class="clip-text">{clip["text"][:80]}{"..." if len(clip["text"]) > 80 else ""}</span>
            </div>"""

        clues_html = ""
        if spk["clues"]:
            clues_items = "".join(f"<li>{c}</li>" for c in spk["clues"])
            clues_html = f'<ul class="clues">{clues_items}</ul>'

        card = f"""
        <div class="card" data-speaker="{spk["id"]}">
            <div class="card-header">
                <h3>{spk["id"]} <span class="stats">{spk["count"]}段 ({spk["pct"]:.1f}%)</span></h3>
                <div class="name-input">
                    <label>讲话人姓名：</label>
                    <input type="text" value="{spk["predicted"]}" data-speaker="{spk["id"]}" class="speaker-name">
                    <select class="quick-val" onchange="applyQuick(this)">
                        <option value="">快捷值…</option>
                        <option value="混合多人(声音未录入)">混合多人</option>
                        <option value="(声音未录入)">声音未录入</option>
                        <option value="(幻听/噪音)">幻听/噪音</option>
                        {_build_merge_options(spk["id"], speakers_data)}
                    </select>
                </div>
            </div>
            <div class="clips">{clips_html}</div>
            {clues_html}
        </div>"""
        cards_html.append(card)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>讲话人识别</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, "Microsoft YaHei", sans-serif; background: #f5f5f5; padding: 20px; max-width: 960px; margin: 0 auto; }}
h1 {{ margin-bottom: 8px; color: #333; }}
.subtitle {{ color: #666; margin-bottom: 24px; font-size: 14px; }}
.card {{ background: #fff; border-radius: 8px; padding: 20px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
.card-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 8px; }}
.card-header h3 {{ font-size: 18px; color: #333; }}
.stats {{ font-size: 13px; color: #888; font-weight: normal; }}
.name-input label {{ font-size: 14px; color: #555; }}
.speaker-name {{ font-size: 15px; padding: 4px 8px; border: 1px solid #ddd; border-radius: 4px; width: 200px; }}
.speaker-name:focus {{ border-color: #4472C4; outline: none; box-shadow: 0 0 0 2px rgba(68,114,196,0.2); }}
.quick-val {{ font-size: 12px; padding: 3px 4px; border: 1px solid #ddd; border-radius: 4px; color: #888; background: #fafafa; cursor: pointer; }}
.clips {{ display: flex; flex-direction: column; gap: 8px; }}
.clip {{ display: flex; align-items: center; gap: 10px; padding: 6px 0; border-bottom: 1px solid #f0f0f0; flex-wrap: wrap; }}
.clip-label {{ font-size: 12px; color: #4472C4; min-width: 120px; white-space: nowrap; }}
.clip audio {{ height: 32px; }}
.clip-text {{ font-size: 13px; color: #666; flex: 1; min-width: 200px; }}
.clues {{ margin-top: 10px; padding-left: 20px; font-size: 13px; color: #555; }}
.clues li {{ margin-bottom: 4px; }}
.actions {{ position: sticky; bottom: 0; background: #fff; padding: 16px; border-radius: 8px; box-shadow: 0 -2px 8px rgba(0,0,0,0.1); display: flex; gap: 12px; justify-content: center; margin-top: 20px; }}
.btn {{ padding: 10px 24px; border: none; border-radius: 6px; font-size: 15px; cursor: pointer; }}
.btn-primary {{ background: #4472C4; color: #fff; }}
.btn-primary:hover {{ background: #3a62a8; }}
.btn-secondary {{ background: #e8e8e8; color: #333; }}
</style>
</head>
<body>
<h1>讲话人识别</h1>
<p class="subtitle">听音频片段，确认或修改每个讲话人的姓名，然后点击"保存"</p>

{"".join(cards_html)}

<div class="actions">
    <button class="btn btn-primary" onclick="saveSpeakerMap()">保存 speaker-map.json</button>
    <button class="btn btn-secondary" onclick="copyToClipboard()">复制到剪贴板</button>
</div>

<script>
function applyQuick(sel) {{
    const card = sel.closest('.card');
    const input = card.querySelector('.speaker-name');
    if (sel.value) {{ input.value = sel.value; }}
    sel.selectedIndex = 0;
}}

function collectMap() {{
    const inputs = document.querySelectorAll('.speaker-name');
    const map = {{}};
    inputs.forEach(input => {{
        const spk = input.dataset.speaker;
        const name = input.value.trim();
        if (name && name !== '？' && !name.includes('未能识别')) {{
            map[spk] = name;
        }}
    }});
    return map;
}}

function saveSpeakerMap() {{
    const map = collectMap();
    const json = JSON.stringify(map, null, 2);
    // Try to save via local server first (auto-save to correct path)
    fetch('/save-speaker-map', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:json}})
    .then(r => r.ok ? r.text() : Promise.reject(r))
    .then(msg => {{ alert('✓ 已保存到 ' + msg); }})
    .catch(() => {{
        // Fallback: download as file
        const blob = new Blob([json], {{ type: 'application/json' }});
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = 'speaker-map.json';
        a.click();
    }});
}}

function copyToClipboard() {{
    const map = collectMap();
    const json = JSON.stringify(map, null, 2);
    navigator.clipboard.writeText(json).then(() => {{
        alert('已复制到剪贴板');
    }});
}}
</script>
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(description="Generate speaker identification HTML page")
    parser.add_argument("--transcript", required=True, help="Transcript JSON file")
    parser.add_argument("--audio", required=True, help="Audio file (MP3/WAV)")
    parser.add_argument("--output", required=True, help="Output HTML file")
    parser.add_argument("--speakers-md", default=None, help="Speaker profile cards markdown file")
    parser.add_argument("--clips-dir", default=None, help="Directory for audio clips (default: <output>_clips/)")
    parser.add_argument("--open", action="store_true", help="Open HTML in default browser after generation")
    args = parser.parse_args()

    transcript = load_transcript(args.transcript)
    segments = transcript.get("segments", [])
    total_segs = len(segments)

    if total_segs == 0:
        print("No segments found in transcript.")
        return

    # Load speaker profiles if available
    speaker_profiles = load_speakers_md(args.speakers_md)

    # Determine clips directory
    clips_dir = Path(args.clips_dir) if args.clips_dir else Path(args.output).with_suffix("") / "_clips"
    clips_dir = Path(str(args.output).replace(".html", "_clips"))
    clips_dir.mkdir(parents=True, exist_ok=True)

    # Analyze speakers
    speaker_counts = defaultdict(int)
    for seg in segments:
        speaker_counts[seg["speaker"]] += 1

    # Sort by count descending
    sorted_speakers = sorted(speaker_counts.items(), key=lambda x: -x[1])

    # Build speaker data
    speakers_data = []
    for spk_id, count in sorted_speakers:
        if count < 3:
            continue  # Skip very minor speakers

        pct = count / total_segs * 100
        profile = speaker_profiles.get(spk_id, {})
        predicted = profile.get("predicted", "")
        clues = profile.get("clues", [])

        # Select and cut clips
        clip_selections = select_clips(segments, spk_id)
        clips = []
        for i, (seg, label) in enumerate(clip_selections):
            clip_filename = f"{spk_id}_{i}.mp3"
            clip_path = clips_dir / clip_filename
            try:
                cut_clip(args.audio, seg["start"], seg["end"], clip_path)
                clips.append({
                    "label": label,
                    "time": format_time(seg["start"]),
                    "text": seg.get("text", ""),
                    "path": f"{clips_dir.name}/{clip_filename}",
                })
            except Exception as e:
                print(f"  Warning: failed to cut clip for {spk_id} at {seg['start']:.1f}s: {e}")

        speakers_data.append({
            "id": spk_id,
            "count": count,
            "pct": pct,
            "predicted": predicted,
            "clues": clues,
            "clips": clips,
        })

    # Generate HTML
    html = generate_html(speakers_data, clips_dir.name)
    output_path = Path(args.output)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Generated: {output_path}")
    print(f"  Speakers: {len(speakers_data)}")
    print(f"  Clips: {sum(len(s['clips']) for s in speakers_data)}")
    print(f"  Clips dir: {clips_dir}")

    if args.open:
        # Start a local server that serves the HTML + clips and accepts POST to save speaker-map
        save_path = output_path.with_name(output_path.stem.replace("_identify", "") + "_speaker-map.json")
        serve_dir = output_path.parent
        _start_save_server(serve_dir, output_path.name, save_path)


def _start_save_server(serve_dir, html_name, save_path):
    """Serve HTML + clips locally, accept POST /save-speaker-map to write file."""
    import http.server
    import threading

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(serve_dir), **kw)

        def do_POST(self):
            if self.path == "/save-speaker-map":
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                with open(save_path, "wb") as f:
                    f.write(body)
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(str(save_path).encode())
                print(f"  Saved speaker-map to: {save_path}")
            else:
                self.send_error(404)

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{port}/{html_name}"
    print(f"  Serving at: {url}")
    print(f"  Speaker-map will save to: {save_path}")
    webbrowser.open(url)
    # Track file modification to detect Save
    initial_mtime = save_path.stat().st_mtime if save_path.exists() else 0
    print(f"  Waiting for Save button click (Ctrl+C to stop)...")
    try:
        while True:
            time.sleep(1)
            if save_path.exists() and save_path.stat().st_mtime > initial_mtime:
                time.sleep(2)  # brief grace period for re-saves
                print(f"  Speaker-map saved. Server stopping.")
                break
    except KeyboardInterrupt:
        pass
    srv.shutdown()


if __name__ == "__main__":
    main()
