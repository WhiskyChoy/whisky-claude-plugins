#!/usr/bin/env python3
"""
Meeting audio transcription with speaker diarization using FunASR.

Usage:
    python funasr_transcribe.py --check
    python funasr_transcribe.py --input audio.mp3 --output result.json
    python funasr_transcribe.py --input ./unified/audio/ --output ./unified/transfer/ --progress-ui

Outputs per file:
    <name>.json  — structured transcription with speaker labels and timestamps
    <name>.txt   — plain text with speaker labels
"""

import argparse
import json
import logging
import os
import sys
import threading
import time
import wave
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════════════
#  PROGRESS SYSTEM — Three tiers:
#    Tier 1: Overall (across all files)
#    Tier 2: Per-file (0-100%, phase-weighted)
#    Tier 3: Current step within file (step_done/step_total)
# ═══════════════════════════════════════════════════════════════════════════════

_state = {
    "status": "initializing",  # initializing | loading_model | transcribing | done | error
    "elapsed": 0,              # total wall-clock seconds since start
    "error": None,

    # Tier 1: files
    "total_files": 0,
    "files": [],               # [{name, duration, status, elapsed, segments, speakers}]

    # Tier 2: current file
    "file_index": 0,
    "file_name": "",
    "file_duration": "",
    "file_elapsed": 0,
    "file_eta": 0,
    "file_pct": 0,             # 0-100, phase-weighted, monotonically increasing

    # Tier 3: current step
    "step_name": "",
    "step_done": 0,
    "step_total": 0,
}
_lock = threading.Lock()
_start_time = 0  # set once in main()


def _set(**kw):
    with _lock:
        _state.update(kw)
        _state["elapsed"] = time.time() - _start_time if _start_time else 0


def _get():
    with _lock:
        d = dict(_state)
        d["elapsed"] = time.time() - _start_time if _start_time else 0
        return d


# ── Tier 2: time-based file progress ──
# tqdm bars on GPU complete in seconds — useless for file_pct.
# Instead, estimate total time from audio duration × RTF, advance linearly.
_rtf_estimate = 0.15  # default RTF on GPU; updated after first file completes


def _reset_file_progress():
    global _tqdm_count
    _tqdm_count = 0
    _set(file_pct=0, file_elapsed=0, file_eta=0, step_done=0)


# ── Tier 3: tqdm instance counter ──
# FunASR creates hundreds of tqdm instances during processing.
# Just count them to show the system is working.
_tqdm_count = 0


def _tick_tqdm(total):
    global _tqdm_count
    _tqdm_count += 1
    _set(step_done=_tqdm_count)


# ── tqdm monkey-patch ──

_orig_tqdm = None
_devnull_file = None


def _install_tqdm_hook():
    global _orig_tqdm, _devnull_file
    import tqdm as m
    _orig_tqdm = m.tqdm
    _devnull_file = open(os.devnull, "w")

    class _T(_orig_tqdm):
        def __init__(self, *a, **kw):
            kw["file"] = _devnull_file
            kw.pop("disable", None)
            super().__init__(*a, **kw)
            if _get()["status"] == "transcribing":
                _tick_tqdm(self.total)

    m.tqdm = _T
    try:
        import tqdm.auto as ta
        ta.tqdm = _T
    except ImportError:
        pass


def _uninstall_tqdm_hook():
    global _orig_tqdm, _devnull_file
    if _orig_tqdm:
        import tqdm as m
        m.tqdm = _orig_tqdm
        try:
            import tqdm.auto as ta
            ta.tqdm = _orig_tqdm
        except ImportError:
            pass
        _orig_tqdm = None
    if _devnull_file:
        _devnull_file.close()
        _devnull_file = None


# ═══════════════════════════════════════════════════════════════════════════════
#  PROGRESS UI — HTML + tiny HTTP server
# ═══════════════════════════════════════════════════════════════════════════════

_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><title>会议转录进度</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,"Microsoft YaHei",sans-serif;background:#f0f2f5;display:flex;justify-content:center;padding:40px 20px}
.c{max-width:640px;width:100%}
h1{font-size:22px;color:#333;margin-bottom:20px}
.box{background:#fff;border-radius:10px;padding:20px;margin-bottom:14px;box-shadow:0 1px 3px rgba(0,0,0,.08)}
.lbl{font-size:14px;color:#666;margin-bottom:8px}
.bar{background:#e8e8e8;border-radius:6px;height:12px;overflow:hidden}
.bar-sm{height:8px}
.fb{height:100%;border-radius:6px;transition:width .5s}
.fb-b{background:linear-gradient(90deg,#4472C4,#5B9BD5)}
.fb-g{background:linear-gradient(90deg,#52c41a,#73d13d)}
.row{display:flex;justify-content:space-between;margin-top:5px;font-size:12px;color:#999}
.card{background:#fff;border-radius:8px;padding:14px 18px;margin-bottom:10px;box-shadow:0 1px 3px rgba(0,0,0,.08)}
.hdr{display:flex;justify-content:space-between;align-items:center}
.fn{font-size:14px;color:#333;font-weight:500}
.fm{font-size:12px;color:#888;margin-top:2px}
.bd{font-size:11px;padding:2px 8px;border-radius:10px}
.bp{background:#f0f0f0;color:#999}.ba{background:#e8f4fd;color:#1890ff}
.bd-ok{background:#f0f9eb;color:#52c41a}.bs{background:#fff7e6;color:#faad14}.be{background:#fff1f0;color:#ff4d4f}
.fp{margin-top:10px}
.sl{font-size:12px;color:#1890ff;margin-bottom:4px}
.dn{border-radius:10px;padding:20px;text-align:center;font-size:16px;margin-bottom:14px}
.dok{background:#f0f9eb;border:1px solid #b7eb8f;color:#52c41a}
.der{background:#fff1f0;border:1px solid #ffa39e;color:#ff4d4f}
.sp{display:inline-block;width:12px;height:12px;border:2px solid #1890ff;border-top-color:transparent;border-radius:50%;animation:r .8s linear infinite;vertical-align:middle;margin-right:4px}
@keyframes r{to{transform:rotate(360deg)}}
</style></head><body><div class="c"><h1>会议转录进度</h1><div id="a"></div></div>
<script>
const F=s=>s<10?'0'+s:s, T=s=>{s=Math.round(s);const m=Math.floor(s/60);return F(m)+':'+F(s%60)};
const B=s=>({pending:['待处理','bp'],active:['<span class="sp"></span>转录中','ba'],done:['✓ 完成','bd-ok'],skipped:['已跳过','bs'],error:['✗ 失败','be']}[s]||['—','']);

async function P(){try{
const d=await(await fetch('/progress')).json(),a=document.getElementById('a');
const done=d.status==='done',err=d.status==='error',ld=d.status==='loading_model',tr=d.status==='transcribing';
const cf=d.files.filter(f=>f.status==='done'||f.status==='skipped').length;
const op=d.total_files?Math.round((cf*100+(tr?d.file_pct:0))/d.total_files):0;
let h='';

// banners
if(done)h+='<div class="dn dok">✓ 全部转录完成</div>';
if(err)h+=`<div class="dn der">✗ ${d.error||'出错'}</div>`;

// Tier 1: overall
const ol=ld?'<span class="sp"></span>加载模型中...':tr?`<span class="sp"></span>转录中 (${cf}/${d.total_files})`:done?'全部完成':'初始化...';
h+=`<div class="box"><div class="lbl">${ol}</div><div class="bar"><div class="fb fb-b" style="width:${done?100:op}%"></div></div><div class="row"><span>${done?100:op}%</span><span>总用时 ${T(d.elapsed)}</span></div>`;

// model loading sub-progress
if(ld&&d.step_name){
  h+=`<div style="margin-top:10px"><div class="sl">${d.step_name} (${d.step_done}/${d.step_total})</div><div class="bar bar-sm"><div class="fb fb-g" style="width:${d.step_total?Math.round(d.step_done/d.step_total*100):0}%"></div></div></div>`;
}
h+='</div>';

// file cards
for(const f of d.files){
  const ac=f.status==='active';
  const [bt,bc]=B(f.status);
  h+=`<div class="card"><div class="hdr"><div><div class="fn">${f.name}</div><div class="fm">${f.duration||''}`;
  if(f.status==='done')h+=` · ${T(f.elapsed)} · ${f.segments}段 · ${f.speakers}人`;
  h+=`</div></div><span class="bd ${bc}">${bt}</span></div>`;

  // Tier 2 + 3: active file progress
  if(ac){
    const eta=d.file_eta>0?` · 预计剩余 ${T(d.file_eta)}`:'';
    // Tier 2: file progress bar
    h+=`<div class="fp"><div class="bar"><div class="fb fb-g" style="width:${d.file_pct}%"></div></div>`;
    h+=`<div class="row"><span>${d.file_pct}% · ${T(d.file_elapsed)}${eta}</span></div>`;
    // Tier 3: processing counter
    if(d.step_done>0){
      h+=`<div style="margin-top:6px;font-size:12px;color:#1890ff"><span class="sp"></span>已处理 ${d.step_done} 个片段</div>`;
    }
    h+='</div>';
  }
  h+='</div>';
}
a.innerHTML=h;
if(done||err){document.title=done?'✓ 转录完成':'✗ 转录失败';return}
}catch(e){}
setTimeout(P,1000)}
P();
</script></body></html>"""


class _Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers()
            self.wfile.write(_HTML.encode())
        elif self.path == "/progress":
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Cache-Control", "no-cache"); self.end_headers()
            self.wfile.write(json.dumps(_get(), ensure_ascii=False).encode())
        else:
            self.send_error(404)
    def log_message(self, *a): pass


def _start_server():
    srv = HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


# ═══════════════════════════════════════════════════════════════════════════════
#  CORE TRANSCRIPTION LOGIC (no progress concerns below this line)
# ═══════════════════════════════════════════════════════════════════════════════

def _suppress_noise():
    for name in ("jieba", "root", "funasr", "modelscope", "transformers"):
        logging.getLogger(name).setLevel(logging.ERROR)
    logging.getLogger().setLevel(logging.ERROR)
    os.environ.pop("TQDM_DISABLE", None)


def load_model(device="cuda:0"):
    _suppress_noise()
    try:
        from funasr import AutoModel
    except ImportError:
        print("ERROR: FunASR not installed. pip install funasr torch torchaudio modelscope", file=sys.stderr)
        sys.exit(1)

    subs = [("paraformer-zh", "ASR 语音识别模型"), ("fsmn-vad", "VAD 语音检测模型"),
            ("ct-punc", "标点恢复模型"), ("cam++", "说话人识别模型")]
    total = len(subs) + 1

    for i, (name, label) in enumerate(subs):
        _set(step_name=label, step_done=i, step_total=total)
        print(f"  [{i+1}/{total}] {label}...", end="", flush=True)
        AutoModel(model=name, device=device, disable_update=True)
        print(" OK")
        _set(step_done=i + 1)

    _set(step_name="组装完整模型", step_done=total - 1, step_total=total)
    print(f"  [{total}/{total}] 组装完整模型...", end="", flush=True)
    old = sys.stdout; sys.stdout = open(os.devnull, "w")
    try:
        model = AutoModel(model="paraformer-zh", vad_model="fsmn-vad",
                          vad_kwargs={"max_single_segment_time": 60000},
                          punc_model="ct-punc", spk_model="cam++",
                          device=device, disable_update=True)
    finally:
        sys.stdout.close(); sys.stdout = old
    print(" OK")
    _set(step_name="模型就绪", step_done=total, step_total=total)
    return model


def get_duration(path):
    try:
        import torchaudio
        info = torchaudio.info(str(path))
        return info.num_frames / info.sample_rate
    except Exception:
        try:
            with wave.open(str(path), "rb") as w:
                return w.getnframes() / float(w.getframerate())
        except Exception:
            return None


def fmt_time(s):
    h, s = int(s // 3600), s % 3600
    m, s = int(s // 60), int(s % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def transcribe_file(model, audio_path):
    global _rtf_estimate
    dur = get_duration(audio_path)
    print(f"  Duration: {fmt_time(dur) if dur else '?'}")
    print(f"  Transcribing...", end="", flush=True)

    _reset_file_progress()
    _set(file_duration=fmt_time(dur) if dur else "?")

    # Estimate total processing time for smooth Tier 2 progress
    est_total = dur * _rtf_estimate if dur else 60

    result_holder, error_holder = [None], [None]
    t0 = time.time()

    def run():
        try:
            result_holder[0] = model.generate(input=str(audio_path), batch_size_s=300, batch_size_threshold_s=60)
        except Exception as e:
            error_holder[0] = e

    t = threading.Thread(target=run)
    t.start()

    while t.is_alive():
        t.join(timeout=1.0)
        el = time.time() - t0
        # Tier 2: time-based, linear toward 95%, never exceed 95% before done
        pct = min(int(el / est_total * 95), 95) if est_total > 0 else min(int(el), 95)
        eta = max(est_total - el, 0)
        _set(file_pct=pct, file_elapsed=el, file_eta=eta)

    elapsed = time.time() - t0
    # Update RTF estimate for next file
    if dur and dur > 0:
        _rtf_estimate = elapsed / dur

    if error_holder[0]:
        print(f" ERROR: {error_holder[0]}")
        return None, elapsed
    res = result_holder[0]
    if not res:
        print(" FAILED")
        return None, elapsed

    result = res[0]
    rtf = elapsed / dur if dur else 0
    print(f" done ({elapsed:.1f}s, RTF={rtf:.3f})")
    si = result.get("sentence_info", [])
    spks = set(s.get("spk", -1) for s in si)
    print(f"  Segments: {len(si)}, Speakers: {len(spks)}")
    return result, elapsed


def parse_result(result, audio_path):
    text = result.get("text", "")
    si = result.get("sentence_info", [])
    segs, spks = [], set()
    for s in si:
        spk = s.get("spk", -1)
        label = f"SPEAKER_{spk:02d}" if spk >= 0 else "UNKNOWN"
        spks.add(label)
        segs.append({"speaker": label, "start": s.get("start", 0) / 1000, "end": s.get("end", 0) / 1000, "text": s.get("text", "")})

    lines, cur, buf = [], None, []
    for s in segs:
        if s["speaker"] != cur:
            if cur: lines.append(f"[{cur}] {''.join(buf)}")
            cur, buf = s["speaker"], [s["text"]]
        else:
            buf.append(s["text"])
    if cur: lines.append(f"[{cur}] {''.join(buf)}")

    return {"file": Path(audio_path).name, "speakers": sorted(spks), "segments": segs,
            "full_text": text, "labeled_text": "\n\n".join(lines)}


def apply_speaker_map(out, m):
    if not m: return out
    for s in out["segments"]:
        if s["speaker"] in m: s["speaker"] = m[s["speaker"]]
    out["speakers"] = [m.get(s, s) for s in out["speakers"]]
    for old, new in m.items():
        out["labeled_text"] = out["labeled_text"].replace(f"[{old}]", f"[{new}]")
    return out


def save_output(out, path):
    path = Path(path)
    with open(path.with_suffix(".json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"  JSON: {path.with_suffix('.json')}")
    lines = [f"[{fmt_time(s['start'])} - {fmt_time(s['end'])}] [{s['speaker']}] {s['text']}" for s in out["segments"]]
    with open(path.with_suffix(".txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  TXT:  {path.with_suffix('.txt')}")


def check_models(device="cuda:0"):
    print("Checking FunASR models...")
    model = load_model(device=device)
    print("  Running sanity check...", end="", flush=True)
    import numpy as np
    try:
        model.generate(input=np.zeros(16000, dtype=np.float32), batch_size_s=1, disable_pbar=True)
        print(" PASSED")
    except Exception as e:
        print(f" WARNING - {e}")
    print("\nAll models ready.")


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    global _start_time

    ap = argparse.ArgumentParser(description="Transcribe meeting audio with FunASR")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--input", default=None)
    ap.add_argument("--output", default=None)
    ap.add_argument("--device", default="cuda:0")
    ap.add_argument("--speaker-map", default=None)
    ap.add_argument("--progress-ui", action="store_true")
    args = ap.parse_args()

    if args.check:
        check_models(args.device); return
    if not args.input or not args.output:
        ap.error("--input and --output required (or use --check)")

    inp, outp = Path(args.input), Path(args.output)

    spk_map = {}
    if args.speaker_map and Path(args.speaker_map).exists():
        with open(args.speaker_map, "r", encoding="utf-8") as f:
            spk_map = json.load(f)

    if inp.is_dir():
        files = sorted(p for p in inp.iterdir() if p.suffix.lower() in (".wav", ".mp3", ".m4a", ".flac", ".ogg"))
        outp.mkdir(parents=True, exist_ok=True)
        batch = True
    else:
        files = [inp]; batch = False

    if not files:
        print("No audio files."); return

    total = len(files)
    finfos = []
    for f in files:
        d = get_duration(f)
        o = (outp / f.stem) if batch else outp.with_suffix("")
        finfos.append({"name": f.name, "duration": fmt_time(d) if d else "—",
                        "status": "skipped" if o.with_suffix(".json").exists() else "pending",
                        "elapsed": 0, "segments": 0, "speakers": 0})

    _start_time = time.time()
    _set(status="loading_model", total_files=total, files=finfos)

    _install_tqdm_hook()

    srv = None
    if args.progress_ui:
        import webbrowser
        srv, port = _start_server()
        url = f"http://127.0.0.1:{port}"
        print(f"Progress UI: {url}")
        webbrowser.open(url)

    # Load model in thread to keep elapsed ticking
    print(f"Loading model on {args.device}...")
    holder = [None]
    def ld(): holder[0] = load_model(args.device)
    lt = threading.Thread(target=ld); lt.start()
    while lt.is_alive():
        lt.join(timeout=1.0)
    model = holder[0]
    print("Model loaded.\n")
    time.sleep(0.5)

    _set(status="transcribing", step_name="", step_done=0, step_total=0)

    for idx, af in enumerate(files):
        fi = finfos[idx]
        if fi["status"] == "skipped":
            print(f"[{idx+1}/{total}] {af.name} — skipped")
            _set(file_index=idx + 1, files=finfos)
            continue

        fi["status"] = "active"
        _set(file_index=idx, file_name=af.name, files=finfos)
        print(f"[{idx+1}/{total}] {af.name}")

        o = (outp / af.stem) if batch else outp.with_suffix("")
        result, el = transcribe_file(model, af)

        if result is None:
            fi["status"] = "error"; fi["elapsed"] = el
            _set(files=finfos); continue

        out = apply_speaker_map(parse_result(result, af), spk_map)
        save_output(out, o)
        fi.update(status="done", elapsed=el, segments=len(out["segments"]), speakers=len(out["speakers"]))
        _set(file_index=idx + 1, file_pct=100, files=finfos)
        print()

    _set(status="done", file_index=total, files=finfos)
    _uninstall_tqdm_hook()
    print("Done.")

    if srv:
        print("Progress page stays open 30s (Ctrl+C to close)...")
        try: time.sleep(30)
        except KeyboardInterrupt: pass
        srv.shutdown()


if __name__ == "__main__":
    main()
