#!/usr/bin/env python3
"""
Clip Picker: propose Shorts candidates from one of your long videos.

Pipeline: timestamped YouTube captions -> sentence-aligned 20-45s windows ->
heuristic score -> (optional) local LLM picks the best and writes a hook ->
clips.md / clips.json with timestamps -> (optional) ffmpeg renders 9:16 files
with burned-in captions from a local copy of the video.

Usage:
  python clip_picker.py VIDEO_ID_OR_URL                       # propose clips
  python clip_picker.py VIDEO_ID --llm                       # + Ollama LLM rerank/hooks
  python clip_picker.py VIDEO_ID --render source.mp4 --pick 1 3   # render chosen
"""
import argparse
import json
import os
import random
import re
import subprocess
import sys
import time

OUT_ROOT = "./output/clips"

from clip_paths import folder_for
MIN_S, MAX_S = 20, 45

HOOK_WORDS = {"never", "stop", "mistake", "secret", "truth", "actually", "nobody",
              "surprising", "change", "changes", "cut", "new", "rule", "loophole",
              "avoid", "save", "pay", "tax", "ruling", "deadline", "before", "why"}
WEAK_START = {"and", "so", "but", "also", "because", "which", "that", "this", "it",
              "they", "he", "she", "then", "or", "well", "now", "anyway"}
FILLER = re.compile(r"\b(um+|uh+|you know|sort of|kind of|subscribe|like and)\b", re.I)


def video_id(s):
    m = re.search(r"(?:v=|youtu\.be/|shorts/)([\w-]{11})", s)
    return m.group(1) if m else s


_CAPTIONS_BLOCKED = False  # once YouTube blocks the caption endpoint, stop asking it for this run


def enable_cuda_dlls():
    """Let faster-whisper find the cuBLAS/cuDNN DLLs installed via pip (nvidia-cublas-cu12, nvidia-cudnn-cu12)."""
    import glob
    import site
    for sp in site.getsitepackages():
        for d in glob.glob(os.path.join(sp, "nvidia", "*", "bin")):
            os.add_dll_directory(d)
            os.environ["PATH"] = d + os.pathsep + os.environ["PATH"]


def whisper_snippets(vid):
    """Fallback: download the audio with yt-dlp and transcribe it locally (segment-level timing)."""
    import wave
    import numpy as np
    enable_cuda_dlls()
    from faster_whisper import WhisperModel
    d = folder_for(OUT_ROOT, vid)
    wav = os.path.join(d, "audio.wav")
    if not os.path.exists(wav):
        m4a = os.path.join(d, "audio.m4a")
        subprocess.run([sys.executable, "-m", "yt_dlp", "-q", "-f", "ba[ext=m4a]/ba", "-o", m4a,
                        f"https://youtu.be/{vid}"], check=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", m4a, "-ac", "1", "-ar", "16000", wav], check=True)
        os.remove(m4a)
    with wave.open(wav) as wf:  # decode here: faster-whisper's own decoder breaks with the installed PyAV
        audio = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    try:
        segs, _ = WhisperModel("small.en", device="cuda", compute_type="float16").transcribe(audio, language="en")
        segs = list(segs)
    except Exception:
        segs, _ = WhisperModel("small.en", device="cpu", compute_type="int8").transcribe(audio, language="en")
        segs = list(segs)
    os.remove(wav)
    return [{"text": s.text.strip(), "start": s.start, "end": s.end} for s in segs if s.text.strip()]


def fetch_snippets(vid):
    global _CAPTIONS_BLOCKED
    clean = lambda t: re.sub(r"\s+", " ", re.sub(r"\[[^\]]*\]|>>", " ", t)).strip()
    if not _CAPTIONS_BLOCKED:
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            tr = YouTubeTranscriptApi().fetch(vid, languages=["en", "en-US", "en-GB"])
            return [{"text": clean(s.text), "start": s.start, "end": s.start + s.duration}
                    for s in tr.snippets if clean(s.text)]
        except Exception as e:
            if type(e).__name__ in ("IpBlocked", "RequestBlocked"):
                _CAPTIONS_BLOCKED = True
                print("  captions blocked by YouTube; transcribing audio locally instead", flush=True)
            else:
                raise
    os.makedirs(folder_for(OUT_ROOT, vid), exist_ok=True)
    return whisper_snippets(vid)


def sentences(snips):
    """Group caption snippets into sentence-ish units that keep their time span."""
    out, cur = [], None
    for s in snips:
        if cur is None:
            cur = dict(s)
        else:
            cur["text"] += " " + s["text"]
            cur["end"] = s["end"]
        if re.search(r"[.!?]['\")]?$", cur["text"]) or cur["end"] - cur["start"] > 12:
            out.append(cur)
            cur = None
    if cur:
        out.append(cur)
    return out


def score(text, dur):
    words = text.split()
    first = re.sub(r"\W", "", words[0]).lower() if words else ""
    sc = 0.0
    lw = [re.sub(r"\W", "", w).lower() for w in words]
    sc += 1.5 * len(HOOK_WORDS.intersection(lw))
    sc += 1.0 * min(len(re.findall(r"\d[\d.,%]*", text)), 4)          # numbers
    sc += 1.0 if "?" in text.split(".")[0] else 0                       # opens with a question
    sc += 0.7 * len(re.findall(r"\b(but|however|instead|except|unless)\b", text, re.I)) ** 0.5
    sc -= 3.0 if first in WEAK_START else 0                             # not self-contained
    sc -= 1.0 * len(FILLER.findall(text))
    sc -= 2.0 if not re.search(r"[.!?]['\")]?$", text.strip()) else 0   # ends mid-sentence
    wps = len(words) / max(dur, 1)
    sc -= 2.0 if wps < 1.8 else 0                                        # dead air / slow
    return round(sc, 2)


def candidates(sents, top=12):
    cands = []
    for i in range(len(sents)):
        for j in range(i, len(sents)):
            dur = sents[j]["end"] - sents[i]["start"]
            if dur > MAX_S:
                break
            if dur < MIN_S:
                continue
            text = " ".join(x["text"] for x in sents[i:j + 1])
            cands.append({"start": round(sents[i]["start"], 1), "end": round(sents[j]["end"], 1),
                          "dur": round(dur, 1), "text": text, "score": score(text, dur)})
    cands.sort(key=lambda c: -c["score"])
    picked = []
    for c in cands:  # drop overlaps so the list is varied
        if all(c["end"] <= p["start"] or c["start"] >= p["end"] for p in picked):
            picked.append(c)
        if len(picked) == top:
            break
    return picked


def llm_rerank(cands, base, model, title):
    import requests
    listing = "\n".join(f"[{i}] ({c['dur']}s) {c['text']}" for i, c in enumerate(cands))
    prompt = (
        f"You pick YouTube Shorts clips from a tax explainer video titled '{title}'.\n"
        "Choose the 3 candidates that work best as standalone Shorts: a strong first 2 seconds, "
        "one clear idea, understandable without the rest of the video. For each write a hook line "
        "of at most 9 words for on-screen text (no dashes, no hype words). Reply with JSON only: "
        '[{"i": <index>, "hook": "...", "why": "..."}]\n\n' + listing)
    r = requests.post(f"{base}/api/chat", timeout=600, json={
        "model": model, "stream": False, "think": False, "keep_alive": "2m",
        "options": {"temperature": 0.3, "num_ctx": 8192},
        "messages": [{"role": "user", "content": prompt}]})
    r.raise_for_status()
    txt = r.json()["message"]["content"]
    picks = json.loads(re.search(r"\[.*\]", txt, re.S).group(0))
    out = []
    for p in picks:
        c = dict(cands[int(p["i"])])
        c["hook"], c["why"] = p.get("hook", ""), p.get("why", "")
        out.append(c)
    return out


def srt_time(t):
    ms = int(round(t * 1000))
    return f"{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}"


def write_srt(path, snips, start, end):
    n = 0
    with open(path, "w", encoding="utf-8") as f:
        for s in snips:
            if s["end"] <= start or s["start"] >= end:
                continue
            n += 1
            f.write(f"{n}\n{srt_time(max(s['start'], start) - start)} --> "
                    f"{srt_time(min(s['end'], end) - start)}\n{s['text']}\n\n")


def render(src, snips, c, idx, outdir):
    srt = f"clip{idx}.srt"
    write_srt(os.path.join(outdir, srt), snips, c["start"], c["end"])
    style = "FontSize=14,Alignment=2,MarginV=90,Bold=1,Outline=2"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-ss", str(c["start"]), "-t", str(c["dur"]),
           "-i", os.path.abspath(src), "-vf",
           f"crop=ih*9/16:ih,scale=1080:1920,subtitles={srt}:force_style='{style}'",
           "-c:v", "libx264", "-crf", "20", "-c:a", "aac", f"clip{idx}.mp4"]
    subprocess.run(cmd, cwd=outdir, check=True)  # cwd=outdir keeps the subtitles path simple
    return os.path.join(outdir, f"clip{idx}.mp4")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", nargs="?")
    ap.add_argument("--batch", metavar="IDS_FILE", help="file with one video id/URL per line (# comments ok)")
    ap.add_argument("--title", default="")
    ap.add_argument("--llm", nargs="?", const="http://localhost:11434", help="Ollama base URL (default http://localhost:11434)")
    ap.add_argument("--model", default="qwen3.6:27b")
    ap.add_argument("--top", type=int, default=12, help="heuristic candidates to keep")
    ap.add_argument("--render", metavar="SOURCE_MP4")
    ap.add_argument("--pick", type=int, nargs="+", help="clip numbers (from clips.md) to render")
    a = ap.parse_args()

    if a.batch:
        ids = [l.split("#")[0].strip() for l in open(a.batch, encoding="utf-8")]
        ids = [video_id(x) for x in ids if x]
        blocked = 0
        for n, v in enumerate(ids, 1):
            if os.path.exists(os.path.join(folder_for(OUT_ROOT, v), "clips.json")):
                continue  # resumable: finished videos are skipped after a crash/restart
            print(f"[{n}/{len(ids)}] {v}", flush=True)
            try:
                run_one(v, a)
                blocked = 0
            except Exception as e:  # no captions, rate limit, LLM down: log and move on
                reason = type(e).__name__ + ": " + (str(e).strip().splitlines() or [""])[0][:120]
                os.makedirs(OUT_ROOT, exist_ok=True)
                with open(os.path.join(OUT_ROOT, "errors.txt"), "a", encoding="utf-8") as f:
                    f.write(f"{v}\t{reason}\n")
                print(f"  failed: {reason}", file=sys.stderr)
                blocked = blocked + 1 if type(e).__name__ in ("IpBlocked", "RequestBlocked") else 0
                if blocked >= 3:  # more requests only prolong the ban
                    sys.exit("YouTube is blocking caption requests from this IP. Stopped; "
                             "re-run the same command in a few hours and it resumes.")
            time.sleep(random.uniform(8, 14))  # slow, jittered: YouTube blocks bursts of caption requests
        return
    run_one(video_id(a.video), a)


def run_one(vid, a):
    outdir = folder_for(OUT_ROOT, vid)
    os.makedirs(outdir, exist_ok=True)
    cache = os.path.join(outdir, "snippets.json")
    if os.path.exists(cache):
        snips = json.load(open(cache, encoding="utf-8"))
    else:
        snips = fetch_snippets(vid)
        json.dump(snips, open(cache, "w", encoding="utf-8"))

    clips_path = os.path.join(outdir, "clips.json")
    if a.render and os.path.exists(clips_path):
        clips = json.load(open(clips_path, encoding="utf-8"))
    else:
        cands = candidates(sentences(snips), a.top)
        clips = cands[:5]
        if a.llm:
            try:
                clips = llm_rerank(cands, a.llm.rstrip("/"), a.model, a.title or vid)
            except Exception as e:
                print(f"LLM rerank failed ({e}); using heuristic order", file=sys.stderr)
        json.dump(clips, open(clips_path, "w", encoding="utf-8"), indent=1)
        with open(os.path.join(outdir, "clips.md"), "w", encoding="utf-8") as f:
            f.write(f"# Clip candidates for {vid}\n\n")
            for n, c in enumerate(clips, 1):
                f.write(f"## {n}. {srt_time(c['start'])[:8]} to {srt_time(c['end'])[:8]} "
                        f"({c['dur']}s, score {c['score']})\n")
                if c.get("hook"):
                    f.write(f"**Hook:** {c['hook']}\n\n")
                f.write(f"{c['text']}\n\n")
        print(f"Wrote {outdir}/clips.md ({len(clips)} candidates)")

    if a.render:
        for n in a.pick or [1]:
            print("Rendered", render(a.render, snips, clips[n - 1], n, outdir))


if __name__ == "__main__":
    main()
