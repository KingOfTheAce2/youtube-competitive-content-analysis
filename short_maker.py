#!/usr/bin/env python3
"""
Short maker: turn chosen moments from clip_picker.py into finished 9:16 Shorts.

For each clip: cut from the source video, transcribe the audio with Whisper for
word-level timing, tighten dead air into jump cuts, crop to 9:16 following the
speaker's face (smoothed, static when the speaker barely moves), keep the
source's own burned-in lower thirds out of frame, put the hook in a band above
the head, burn in word-highlight captions inside the Shorts safe zone,
normalise loudness, export mp4 plus a .txt with title, description and hashtags.

Source video: --source FILE (best quality: your original export), otherwise the
video is downloaded once with yt-dlp (up to 1080p) into output/clips/<id>/.

Usage:
  python short_maker.py VIDEO_ID --pick 2             # one clip
  python short_maker.py VIDEO_ID --pick 1 3 --source my_original.mp4
  python short_maker.py VIDEO_ID --pick 2 --music private/music   # with background music
  python short_maker.py --decisions clip_decisions.json   # everything marked Keep in the dashboard
  python short_maker.py VIDEO_ID --pick 2 --out scratch --force   # re-render into another folder
  python short_maker.py VIDEO_ID --pick 2 --no-cuts --no-punch     # keep pauses, no zoom changes
"""
import argparse
import glob
import importlib.util
import json
import os
import random
import re
import shutil
import statistics
import subprocess
import sys
from collections import Counter

CLIPS = "./output/clips"
SHORTS = "./output/shorts"

from clip_paths import folder_for, slug
PAD_BEFORE, PAD_AFTER = 0.25, 0.45
OUT_W, OUT_H = 1080, 1920
SAFE_TOP, SAFE_BOTTOM = 150, 1500  # Shorts UI: top bar, and title/channel/progress over the bottom ~20%
SAFE_RIGHT = 150                    # like/comment/share column on the right
MAX_GAP, KEEP_PAD = 0.35, 0.12      # pauses longer than MAX_GAP shrink to 2 x KEEP_PAD (a breath)
PUNCH = 1.12                        # zoom of the punched-in shots
FACE_FPS = 4                        # face samples per second for the follow crop


def run(cmd, **kw):
    try:
        return subprocess.run(cmd, check=True, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", **kw)
    except subprocess.CalledProcessError as e:
        tail = "\n".join((e.stderr or "").strip().splitlines()[-12:])
        raise RuntimeError(f"{os.path.basename(cmd[0])} failed:\n{tail}") from None


def need_tools(download):
    missing = [t for t in ("ffmpeg", "ffprobe") if not shutil.which(t)]
    if missing:
        sys.exit(f"Missing {' and '.join(missing)} on PATH. Install ffmpeg (winget install Gyan.FFmpeg) and reopen the terminal.")
    if download and not importlib.util.find_spec("yt_dlp"):
        sys.exit("yt-dlp is not installed (pip install yt-dlp), or pass --source with a local video file.")


def get_source(vid, source):
    if source:
        if not os.path.exists(source):
            sys.exit(f"--source file not found: {source}")
        return os.path.abspath(source)
    d = folder_for(CLIPS, vid)
    path = os.path.join(d, "source.mp4")
    if not os.path.exists(path):
        need_tools(True)
        print(f"Downloading {vid} (up to 1080p) ...", flush=True)
        run([sys.executable, "-m", "yt_dlp", "-f",
             "bv*[height<=1080][vcodec^=avc1]+ba[ext=m4a]/bv*[height<=1080]+ba/b",
             "--merge-output-format", "mp4", "-o", path, f"https://youtu.be/{vid}"])
    return os.path.abspath(path)


def probe(path):
    out = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
               "stream=width,height,r_frame_rate", "-of", "json", path]).stdout
    s = json.loads(out)["streams"][0]
    num, den = s.get("r_frame_rate", "30/1").split("/")
    return s["width"], s["height"], (float(num) / float(den or 1)) or 30.0


# ---------- framing: face track, burned-in overlays, layout ----------

def face_track(src, start, dur, w, h):
    """[(t, centre x, box top, box height)] every 1/FACE_FPS s; centre None where no face was found."""
    import cv2
    casc = cv2.CascadeClassifier(os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml"))
    if casc.empty():
        return []
    cap = cv2.VideoCapture(src)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    cap.set(cv2.CAP_PROP_POS_MSEC, start * 1000)
    step, k = max(1, round(fps / FACE_FPS)), 0
    f = 540 / h  # detect on a 540p copy: plenty for a talking head, 4x faster
    out = []
    while k < dur * fps and cap.grab():
        if k % step == 0:
            ok, frame = cap.retrieve()
            if not ok:
                break
            g = cv2.cvtColor(cv2.resize(frame, None, fx=f, fy=f), cv2.COLOR_BGR2GRAY)
            faces = casc.detectMultiScale(g, 1.1, 6, minSize=(54, 54))
            out.append((k / fps, [((x + fw / 2) / f, y / f, fh / f) for x, y, fw, fh in faces]))
        k += 1
    cap.release()
    # the speaker is the face that keeps turning up in the same place: drop shelf ornaments and lamps
    big = [max(c, key=lambda r: r[2]) for _, c in out if len(c)]
    if not big:
        return [(t, None, None, None) for t, _ in out]
    ref, size = statistics.median(b[0] for b in big), statistics.median(b[2] for b in big)
    res = []
    for t, c in out:
        c = [r for r in c if abs(r[0] - ref) < 0.15 * w and 0.6 < r[2] / size < 1.6]
        res.append((t, *min(c, key=lambda r: abs(r[0] - ref))) if c else (t, None, None, None))
    return res


def smooth_centres(track, w, cw):
    """Heavily damped crop centre per sample (static if the speaker stays within a small band)."""
    import numpy as np
    t = np.array([s[0] for s in track])
    ok = np.array([s[1] is not None for s in track])
    if ok.sum() < max(3, len(track) * 0.3):
        return t, np.full(len(track), w / 2)
    x = np.interp(t, t[ok], [s[1] for s in track if s[1] is not None])
    x = np.array([np.median(x[max(0, i - 3):i + 4]) for i in range(len(x))])  # kill single-frame misdetections
    k = np.exp(-0.5 * (np.arange(-3 * FACE_FPS, 3 * FACE_FPS + 1) / (1.0 * FACE_FPS)) ** 2)  # Gaussian, sigma 1 s
    x = np.convolve(np.pad(x, len(k) // 2, mode="edge"), k / k.sum(), mode="valid")
    if x.max() - x.min() < 0.12 * cw:  # small sway: a locked-off frame looks calmer than a drifting one
        x[:] = np.median(x)
    return t, x


def overlay_top(src, w, h, x0, x1, n=120):
    """Top row of the source's own burned-in lower-third band (text that comes and goes), else h."""
    import cv2
    import numpy as np
    cap = cv2.VideoCapture(src)
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    y0, prof = int(h * 0.7), []
    for k in range(n):  # sample the whole video: lower thirds are short and may miss the clip itself
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(frames * (k + 0.5) / n))
        ok, frame = cap.read()
        if ok:
            g = cv2.cvtColor(frame[y0:, max(0, x0):min(w, x1)], cv2.COLOR_BGR2GRAY).astype(np.float32)
            prof.append(np.abs(np.diff(g, axis=1)).mean(axis=1))  # horizontal edge density per row
    cap.release()
    if len(prof) < 10:
        return h
    p = np.array(prof)
    hot = ((p - np.median(p, axis=0)) > 3).sum(axis=0) >= max(3, len(p) // 40)  # sharp text in a few frames
    rows = np.nonzero(hot)[0]
    for r in rows:  # topmost hot row of a band that is mostly hot down to the bottom edge
        if hot[r:].mean() > 0.4:
            return y0 + int(r) - int(h * 0.015)
    return h


def plan_layout(w, h, head_top, chin, limit, hook_h):
    """Scale, source window and top band so the head sits under the hook and overlays stay out of frame."""
    want = SAFE_TOP + hook_h + 40 if hook_h else SAFE_TOP  # output y of the top of the head
    s = OUT_H / h
    while True:
        cw, ch0 = OUT_W / s, OUT_H / s
        if head_top * s >= want:  # enough headroom in the source: no band, frame from lower down
            band, y0 = 0, min(head_top - want / s, limit - ch0)
        else:
            band, y0 = int(want - head_top * s) // 2 * 2, 0.0
        ch = (OUT_H - band) / s
        if (y0 + ch <= limit and cw <= w) or s > 3 * OUT_H / h:
            break
        s *= 1.02  # zoom in a touch until the window clears the overlay band
    cap_base = min(SAFE_BOTTOM, max(1330, band + (chin - y0) * s * PUNCH + 160))
    return dict(s=s, cw=cw, ch=ch, y0=max(0.0, y0), band=band, cap_base=cap_base)


# ---------- pacing: jump cuts on dead air ----------

def keep_spans(words, audio, dur, cut=True, sr=16000):
    """Spans of the clip to keep: dead air between words shrinks to a breath, start and end trimmed."""
    import numpy as np
    if not words:
        return [(0.0, dur)]
    hop = sr // 100
    fr = audio[:len(audio) // hop * hop].reshape(-1, hop)
    db = 20 * np.log10(np.sqrt((fr ** 2).mean(axis=1)) + 1e-9)
    quiet = db < max(np.percentile(db, 10) + 8, np.percentile(db, 90) - 30)
    a, b = max(0.0, words[0][1] - 0.1), min(dur, words[-1][2] + 0.3)
    if not cut:
        return [(a, b)]
    # The audio decides where the pauses are (Whisper word edges drift by 0.1-0.4 s); the words only
    # veto a cut that would swallow a soft-spoken word.
    q = quiet.copy()
    for i in range(1, len(q) - 3):  # bridge 10-30 ms blips (lip smacks, clicks) inside a pause
        if not q[i] and q[i - 1] and q[i + 1:i + 4].any():
            q[i] = True
    mids = [(s + e) / 2 for _, s, e in words]
    cuts, i = [], int(a * 100)
    while i < min(len(q), int(b * 100)):
        if not q[i]:
            i += 1
            continue
        j = i
        while j < len(q) and q[j]:
            j += 1
        r0, r1 = i / 100, j / 100
        if r1 - r0 > MAX_GAP and not any(r0 + 0.05 < m < r1 - 0.05 for m in mids):
            cuts.append((r0 + KEEP_PAD, min(r1, b) - KEEP_PAD))
        i = j
    cuts = [(c0, c1) for c0, c1 in cuts if c1 - c0 >= 0.15]  # a tinier cut gains nothing and shows as a jump
    spans, t = [], a
    for c0, c1 in cuts:
        spans.append((t, c0))
        t = c1
    spans.append((t, b))
    return spans


def remap(t, spans):
    """Clip time -> output time after the cuts."""
    off = 0.0
    for a, b in spans:
        if t < a:
            return off
        if t <= b:
            return off + t - a
        off += b - a
    return off


def shots(spans, words, punch=True):
    """Video shots (clip start, end, zoom): zoom alternates at each jump cut and at some sentence starts."""
    starts = [s for (t0, _, _), (_, s, _) in zip(words, words[1:]) if t0[-1] in ".?!"]
    out = []
    for a, b in spans:
        cuts, last = [a], a
        for s in starts:
            s -= 0.05
            if a + 2.5 < s < b - 2.5 and s - last > 2.5:
                cuts.append(s)
                last = s
        out += [(c, d) for c, d in zip(cuts, cuts[1:] + [b])]
    res, z = [], 1.0
    for i, (a, b) in enumerate(out):
        if i and punch and b - a >= 0.7:
            z = PUNCH if z == 1.0 else 1.0
        res.append((a, b, z))
    return res


def x_expr(t0, t1, ts, xs, wz, w):
    """Crop x for one shot as an ffmpeg expression in shot-local t (piecewise linear, 0.5 s keys)."""
    import numpy as np
    n = max(1, int((t1 - t0) / 0.5))
    keys = [(i * (t1 - t0) / n, float(np.interp(t0 + i * (t1 - t0) / n, ts, xs))) for i in range(n + 1)]
    vals = [int(min(max(x - wz / 2, 0), w - wz)) for _, x in keys]
    if max(vals) - min(vals) <= 1:
        return str(vals[0])
    e = str(vals[-1])
    for (ta, _), (tb, _), va, vb in reversed(list(zip(keys, keys[1:], vals, vals[1:]))):
        e = f"if(lt(t,{tb:.3f}),{va}+({vb - va})*(t-{ta:.3f})/{tb - ta:.3f},{e})"
    return e


# ---------- transcription ----------

def transcribe_words(src, start, dur, tmp_wav, prompt=""):
    """(words [(text, start, end)], 16 kHz mono audio) for the clip."""
    run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(start), "-t", str(dur), "-i", src,
         "-vn", "-ac", "1", "-ar", "16000", tmp_wav])
    import wave
    import numpy as np
    from clip_picker import enable_cuda_dlls
    enable_cuda_dlls()
    from faster_whisper import WhisperModel
    with wave.open(tmp_wav) as wf:  # decode here: faster-whisper's own decoder breaks with the installed PyAV
        audio = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    segs = None
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            model = WhisperModel("small.en", device="cuda", compute_type="float16")
            segs = list(model.transcribe(audio, word_timestamps=True, language="en", initial_prompt=prompt or None)[0])
    except Exception as e:
        print(f"  CUDA Whisper unavailable ({str(e)[:80]}), using CPU", flush=True)
    if segs is None:  # CPU is fast enough for 30-45 second clips
        model = WhisperModel("small.en", device="cpu", compute_type="int8")
        segs = list(model.transcribe(audio, word_timestamps=True, language="en", initial_prompt=prompt or None)[0])
    words = []
    for s in segs:
        for w in s.words:
            t = w.word.strip()
            if not t:
                continue
            if words and not w.word.startswith(" "):  # sub-word token such as "U" + ".S.": glue it on
                pt, ps, _ = words[-1]
                words[-1] = (pt + t, ps, w.end)
            else:
                words.append((t, w.start, w.end))
    return words, audio


def trim_tail(words, clip_end, text=""):
    """Drop a half sentence picked up by the end padding, so the Short ends (and loops) on a full stop."""
    norm = lambda t: re.sub(r"[^a-z0-9]", "", t.lower())
    last = norm(text.split()[-1]) if text.split() else ""
    for i in range(len(words) - 1, 0, -1):  # the clip text's own last word, if it closes a sentence near the end
        if words[i][1] < clip_end - 4:
            break
        if last and norm(words[i][0]) == last and words[i][0][-1] in ".?!":
            return words[:i + 1]
    for i in range(len(words) - 1, 0, -1):
        if words[i - 1][0][-1] in ".?!" and words[i][1] >= clip_end - 0.3:
            return words[:i]
        if words[i][1] < clip_end - 0.3:
            break
    return words


# ---------- captions and title card (ASS) ----------

FONT_CANDIDATES = [  # heaviest readable face first; Montserrat if you installed it, else Windows' own
    os.path.expandvars("%LOCALAPPDATA%/Microsoft/Windows/Fonts/Montserrat-Black.ttf"),
    os.path.expandvars("%LOCALAPPDATA%/Microsoft/Windows/Fonts/Montserrat-ExtraBold.ttf"),
    "C:/Windows/Fonts/Montserrat-Black.ttf", "C:/Windows/Fonts/Montserrat-ExtraBold.ttf",
    "C:/Windows/Fonts/ariblk.ttf", "C:/Windows/Fonts/arialbd.ttf",
]
FONT_FILE = next((f for f in FONT_CANDIDATES if os.path.exists(f)), "C:/Windows/Fonts/arialbd.ttf")
CAP_SIZE, HOOK_MAX, HOOK_MIN = 104, 116, 80  # libass sizes (line height), not em
CAP_W = OUT_W - 90 - SAFE_RIGHT - 60  # caption line width that stays clear of the button column
YELLOW = "&H0000D7FF&"


def font_name():
    """(family name libass knows the file by, bold flag): 'Arial' + 'Black' -> 'Arial Black'."""
    try:
        from PIL import ImageFont
        fam, style = ImageFont.truetype(FONT_FILE, 20).getname()
    except Exception:
        return "Arial", -1
    if style in ("Regular", "Bold", "Italic", "Bold Italic"):
        return fam, -1 if "Bold" in style else 0
    return f"{fam} {style}", 0


_fonts = {}


def pil_font(size):
    """PIL font matching libass at font size `size`: libass makes ascent + descent equal the size, PIL the em."""
    from PIL import ImageFont
    if size not in _fonts:
        a, d = ImageFont.truetype(FONT_FILE, 100).getmetrics()
        _fonts[size] = ImageFont.truetype(FONT_FILE, max(1, round(size * 100 / (a + d))))
    return _fonts[size]


def text_width(text, size=CAP_SIZE):
    try:
        return pil_font(size).getlength(text)
    except Exception:
        return len(text) * size * 0.55  # rough fallback for uppercase heavy sans


def wrap_px(text, size, width):
    lines = []
    for word in text.split():
        if lines and text_width(lines[-1] + " " + word, size) <= width:
            lines[-1] += " " + word
        else:
            lines.append(word)
    return lines


def hook_card(hook):
    """(size, lines, card height): the largest size that fits in at most 3 lines."""
    if not hook:
        return 0, [], 0
    for size in range(HOOK_MAX, HOOK_MIN - 1, -6):
        lines = wrap_px(hook.upper(), size, OUT_W - 2 * 110)
        if len(lines) <= 2 or size == HOOK_MIN:
            break
    widest = max(text_width(l, size) for l in lines)  # one very long word can still be wider than the card
    if widest > OUT_W - 2 * 110:
        size = max(40, int(size * (OUT_W - 2 * 110) / widest))
    return size, lines, int(len(lines) * size + 2 * 30)


def ass_time(t):
    cs = int(round(t * 100))
    return f"{cs//360000}:{cs//6000%60:02}:{cs//100%60:02}.{cs%100:02}"


def rounded_rect(w, h, r):
    return (f"m {r} 0 l {w-r} 0 b {w} 0 {w} 0 {w} {r} l {w} {h-r} b {w} {h} {w} {h} {w-r} {h} "
            f"l {r} {h} b 0 {h} 0 {h} 0 {h-r} l 0 {r} b 0 0 0 0 {r} 0")


def build_ass(words, hook, dur, cap_base, hook_secs=0, progress=False):
    """Hook card in the band above the head; chunks of up to 3 words with the spoken word highlighted."""
    font, bold = font_name()
    chunks, cur = [], []
    for w in words:
        if cur and text_width(" ".join(x[0] for x in cur + [w]).upper()) * 1.1 > CAP_W:
            chunks.append(cur)
            cur = []
        cur.append(w)
        if len(cur) >= 3 or w[0][-1] in ".?!,":
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    # Timing: one caption on screen at a time, no overlaps, no flicker across short pauses.
    spans = []
    for k, chunk in enumerate(chunks):
        nxt = chunks[k + 1][0][1] if k + 1 < len(chunks) else dur
        end = chunk[-1][2] + 0.15
        if nxt - chunk[-1][2] < 0.6:
            end = nxt
        spans.append((chunk[0][1], min(end, nxt)))
    cap_x = 90 + CAP_W // 2 + 30
    head = (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: %d\nPlayResY: %d\nWrapStyle: 2\nScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\nFormat: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,"
        "Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,"
        "MarginL,MarginR,MarginV,Encoding\n"
        f"Style: Cap,{font},{CAP_SIZE},&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,{bold},0,0,0,100,100,1,0,1,7,4,2,90,%d,0,1\n"
        f"Style: Hook,{font},{HOOK_MAX},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,{bold},0,0,0,100,100,0,0,1,0,0,5,0,0,0,1\n"
        "Style: Box,Arial,20,&H26141414,&H26141414,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,5,0,0,0,1\n\n"
        "[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n"
    ) % (OUT_W, OUT_H, SAFE_RIGHT + 60)
    ev = []
    size, lines, card_h = hook_card(hook)
    if lines:
        hend = ass_time(min(hook_secs, dur) if hook_secs else dur)
        cy = SAFE_TOP + card_h // 2
        bw = int(max(text_width(l, size) for l in lines)) + 2 * 46
        # a card that stays the whole Short is static, so the loop back to the start is seamless
        pop = "\\fscx88\\fscy88\\t(0,180,\\fscx100\\fscy100)\\fad(120,200)" if hook_secs else ""
        ev.append(f"Dialogue: 2,{ass_time(0)},{hend},Box,,0,0,0,,{{\\an5\\pos(540,{cy}){pop}\\p1}}"
                  f"{rounded_rect(bw, card_h, 26)}{{\\p0}}")
        txt = "\\N".join(lines)
        ev.append(f"Dialogue: 3,{ass_time(0)},{hend},Hook,,0,0,0,,{{\\an5\\pos(540,{cy}){pop}"
                  f"\\fs{size}}}{txt}")
    for chunk, (c_start, c_end) in zip(chunks, spans):
        for i, (_, s, e) in enumerate(chunk):
            s = c_start if i == 0 else s
            end = chunk[i + 1][1] if i + 1 < len(chunk) else c_end
            if end - s < 0.01:
                continue
            # shrink the whole chunk if even one word at 112% pop would pass the caption width
            line = " ".join(t for t, _, _ in chunk).upper()
            cw_px = text_width(line) * 1.12 + len(line) * 1.2 + 7 * 2  # pop scale + style Spacing + outline
            fs = CAP_SIZE if cw_px <= CAP_W else max(20, int(CAP_SIZE * CAP_W / cw_px))
            pop = f"{{\\c{YELLOW}\\fscx112\\fscy112\\t(0,110,\\fscx104\\fscy104)}}"
            text =" ".join((pop + t.upper() + "{\\c&HFFFFFF&\\fscx100\\fscy100}") if j == i else t.upper()
                            for j, (t, _, _) in enumerate(chunk))
            ev.append(f"Dialogue: 0,{ass_time(s)},{ass_time(end)},Cap,,0,0,0,,{{\\an2\\pos({cap_x},{int(cap_base)})\\fs{fs}}}{text}")
    if progress:  # thin bar along the top edge that fills over the Short
        ev.append(f"Dialogue: 4,{ass_time(0)},{ass_time(dur)},Box,,0,0,0,,{{\\an7\\pos(0,0)\\1c{YELLOW}\\1a&H30&"
                  f"\\clip(0,0,0,10)\\t(0,{int(dur * 1000)},\\clip(0,0,{OUT_W},10))\\p1}}m 0 0 l {OUT_W} 0 {OUT_W} 10 0 10{{\\p0}}")
    return head + "\n".join(ev) + "\n"


# ---------- title, description, hashtags ----------

STOP = set("""a an the and or but if then so of to in on at by for with from as is are was were be been being
this that these those it its it's you your you're i we our they their he she his her them not no do does did
can could may might will would should must have has had just about into over than more most very really what
which who whom when where why how all any some one two three first second third also only even simply because
there here out up down get got make made way ways thing things know want need like lot by way actually""".split())


def write_meta(path, vid, hook, text):
    """Upload-ready title, description and 3-5 hashtags from the hook and transcript (no LLM)."""
    toks = re.findall(r"[a-z0-9$][a-z0-9$'-]*", text.lower())
    htoks = set(re.findall(r"[a-z0-9]+", hook.lower()))
    score = Counter()
    for a, b in zip(toks, toks[1:]):
        if a not in STOP and b not in STOP and len(a + b) > 5 and not a.isdigit():
            score[f"{a} {b}"] += 2 + 3 * (a in htoks and b in htoks)
    for t in toks:
        if t not in STOP and len(t) > 4 and not t.isdigit():
            score[t] += 1 + 2 * (t in htoks)
    tags, seen = [], set()
    for term, n in score.most_common():
        if n < (3 if len(tags) >= 2 else 2) or len(tags) == 4:
            break
        parts = term.split()
        if any(p in seen for p in parts):
            continue
        seen.update(parts)
        tags.append("#" + "".join(p.strip("$'-").capitalize() for p in parts))
    tags.append("#Shorts")
    sents = re.split(r"(?<=[.?!])\s+", text.strip())
    desc = ""
    for s in sents:
        if len(desc) + len(s) > 220:
            break
        desc += (" " if desc else "") + s
    title = hook.strip().rstrip(".")
    title = (title[0].upper() + title[1:])[:95] if title else "Short"
    open(path, "w", encoding="utf-8").write(
        f"Title: {title}\n\nDescription:\n{desc or text[:220]}\n\nFull video: https://youtu.be/{vid}\n\n"
        f"{' '.join(tags)}\n")


# ---------- render ----------

def pick_music(path):
    """A music file, or a random audio file from a folder (royalty-free tracks you have the rights to)."""
    if not path:
        return None
    if os.path.isdir(path):
        files = [f for e in ("mp3", "m4a", "wav", "flac", "ogg") for f in glob.glob(os.path.join(path, f"*.{e}"))]
        return os.path.abspath(random.choice(files)) if files else None
    return os.path.abspath(path)


def make_short(vid, n, clip, src, outdir, music=None, cut=True, punch=True, hook_secs=0, progress=False):
    os.makedirs(outdir, exist_ok=True)
    src = os.path.abspath(src)  # ffmpeg runs inside outdir
    start = max(0.0, clip["start"] - PAD_BEFORE)
    dur = round(clip["end"] + PAD_AFTER - start, 2)
    w, h, fps = probe(src)
    stem = f"{n:02}-{slug(clip.get('hook', '')) or 'clip'}"
    hook = clip.get("hook", "").replace("{", "").replace("}", "")

    # 1. words, then the spans that survive the jump cuts
    wav = os.path.join(outdir, f"{stem}.wav")
    words, audio = transcribe_words(src, start, dur, wav, clip.get("text", "")[:600])  # known text steers numbers and form names
    os.remove(wav)
    words = trim_tail(words, clip["end"] - start, clip.get("text", ""))
    spans = keep_spans(words, audio, dur, cut)
    spans = [(round(a * fps) / fps, round(b * fps) / fps) for a, b in spans]  # frame grid keeps audio and video in step
    spans = [(a, b) for a, b in spans if b - a >= 2 / fps]
    out_dur = sum(b - a for a, b in spans)

    # 2. framing: face track, overlay band, layout
    track = []
    try:
        track = face_track(src, start, dur, w, h)
    except Exception as e:
        print(f"  face detection skipped ({e})", file=sys.stderr)
    found = [s for s in track if s[1] is not None]
    if len(found) >= 3:
        head_top = statistics.quantiles([s[2] - 0.25 * s[3] for s in found], n=10)[0] if len(found) > 10 \
            else min(s[2] - 0.25 * s[3] for s in found)  # Haar boxes start at the brow; hair sits above
        chin = statistics.median(s[2] + s[3] * 1.05 for s in found)
        mid = statistics.median(s[1] for s in found)
    else:
        head_top, chin, mid = h * 0.12, h * 0.55, w / 2
    guess_cw = h * 9 / 16
    limit = overlay_top(src, w, h, int(mid - guess_cw), int(mid + guess_cw))
    L = plan_layout(w, h, max(0.0, head_top), chin, limit, hook_card(hook)[2])
    cw, ch, y0, band, s = L["cw"], L["ch"], L["y0"], L["band"], L["s"]
    ts, xs = smooth_centres(track, w, cw) if track else ([0, dur], [mid, mid])
    moving = max(xs) - min(xs) > 0
    print(f"  clip {n}: {start:.1f}s +{dur}s -> {out_dur:.1f}s after {len(spans) - 1} cuts; "
          f"window {cw:.0f}x{ch:.0f} at y={y0:.0f} ({'face-follow' if moving else 'static'}), "
          f"overlay band from y={limit} of {h}, title band {band}px", flush=True)

    # 3. captions on the output timeline
    out_words = [(t, remap(a, spans), remap(b, spans)) for t, a, b in words]
    ass = f"{stem}.ass"
    open(os.path.join(outdir, ass), "w", encoding="utf-8").write(
        build_ass(out_words, hook, out_dur, L["cap_base"], hook_secs, progress))
    fonts = os.path.join(outdir, "fonts")  # ship the font next to the subtitles so libass never falls back
    os.makedirs(fonts, exist_ok=True)
    if os.path.exists(FONT_FILE):
        shutil.copy(FONT_FILE, fonts)

    # 4. filter graph: one trimmed, cropped, scaled chain per shot, concatenated
    fg_h = OUT_H - band
    sh = [(round(a * fps) / fps, round(b * fps) / fps, z) for a, b, z in shots(spans, words, punch)]
    fc = [f"[0:v]split={len(sh)}" + "".join(f"[s{i}]" for i in range(len(sh)))]
    for i, (a, b, z) in enumerate(sh):
        wz, hz = int(cw / z) // 2 * 2, int(ch / z) // 2 * 2
        yz = int(y0 + (max(head_top, y0) - y0) * (1 - 1 / z))  # zoom about the top of the head: it never rises into the title
        fc.append(f"[s{i}]trim=start={a:.4f}:end={b:.4f},setpts=PTS-STARTPTS,"
                  f"crop={wz}:{hz}:'{x_expr(a, b, ts, xs, wz, w)}':{yz},"
                  f"scale={OUT_W}:{fg_h}:flags=lanczos,setsar=1[v{i}]")
    fc.append("".join(f"[v{i}]" for i in range(len(sh))) + f"concat=n={len(sh)}:v=1:a=0[fg]")
    if band:  # extend the wall above the head: the top rows of the frame, stretched and blurred
        fc.append(f"[fg]split[f1][f2];[f2]crop={OUT_W}:16:0:0,scale={OUT_W}:{band},gblur=sigma=18[bd];"
                  f"[bd][f1]vstack[st]")
    else:
        fc.append("[fg]null[st]")
    fc.append(f"[st]ass={ass}:fontsdir=fonts,format=yuv420p[vo]")
    fc.append(f"[0:a]asplit={len(spans)}" + "".join(f"[t{i}]" for i in range(len(spans))))
    for i, (a, b) in enumerate(spans):  # 12 ms fades at every cut: no clicks
        fc.append(f"[t{i}]atrim=start={a:.4f}:end={b:.4f},asetpts=PTS-STARTPTS,"
                  f"afade=t=in:d=0.012,afade=t=out:st={max(b - a - 0.012, 0):.4f}:d=0.012[a{i}]")
    fc.append("".join(f"[a{i}]" for i in range(len(spans))) + f"concat=n={len(spans)}:v=0:a=1[ac]")
    if music:
        # music loops, sits ~18 dB under the voice and ducks further whenever you speak
        fc.append(f"[ac]asplit[v1][v2];[1:a]atrim=duration={out_dur:.3f},volume=0.25,"
                  f"afade=t=out:st={max(out_dur - 1.5, 0):.3f}:d=1.5[m];"
                  "[m][v1]sidechaincompress=threshold=0.02:ratio=8:attack=20:release=400[md];"
                  "[v2][md]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[ao]")
    else:
        fc.append("[ac]loudnorm=I=-14:TP=-1.5:LRA=11[ao]")
    script = os.path.join(outdir, f"{stem}.filter.txt")
    open(script, "w", encoding="utf-8").write(";\n".join(fc))
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", src]
    if music:
        cmd += ["-stream_loop", "-1", "-i", music]
    cmd += ["-filter_complex_script", os.path.basename(script), "-map", "[vo]", "-map", "[ao]",
            "-r", f"{fps:.3f}", "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", f"{stem}.mp4"]
    try:
        run(cmd, cwd=outdir)  # cwd=outdir keeps the ass= path free of drive-letter colons
    finally:
        os.remove(script)
    write_meta(os.path.join(outdir, f"{stem}.txt"), vid, clip.get("hook", ""),
               " ".join(t for t, _, _ in words) or clip.get("text", ""))
    return os.path.join(outdir, f"{stem}.mp4")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", nargs="?")
    ap.add_argument("--pick", type=int, nargs="+", default=[1], help="clip numbers from clips.md")
    ap.add_argument("--source", help="local video file (skips the download)")
    ap.add_argument("--music", metavar="FILE_OR_FOLDER", help="background track mixed under your voice (ducks while you speak)")
    ap.add_argument("--decisions", metavar="JSON", help="clip_decisions.json exported from the dashboard")
    ap.add_argument("--out", metavar="DIR", help="write Shorts here instead of output/shorts/<video>/")
    ap.add_argument("--force", action="store_true", help="re-render clips that already exist")
    ap.add_argument("--no-cuts", action="store_true", help="keep the pauses (no jump cuts on dead air)")
    ap.add_argument("--no-punch", action="store_true", help="no alternating punch-in zoom at cuts")
    ap.add_argument("--hook-secs", type=float, default=0, help="show the hook card this long (default: whole Short)")
    ap.add_argument("--progress-bar", action="store_true", help="thin progress bar along the top edge")
    a = ap.parse_args()

    jobs = []  # (video_id, clip_number)
    if a.decisions:
        for d in json.load(open(a.decisions, encoding="utf-8")):
            if d.get("decision") == "keep":
                jobs.append((d["video_id"], d["moment"]))
    elif a.video:
        jobs = [(a.video, n) for n in a.pick]
    else:
        ap.error("give a VIDEO_ID or --decisions")
    need_tools(False)

    for vid in dict.fromkeys(v for v, _ in jobs):
        cj = os.path.join(folder_for(CLIPS, vid), "clips.json")
        if not os.path.exists(cj):
            print(f"{vid}: no clips.json yet, run clip_picker.py {vid} first", file=sys.stderr)
            continue
        clips = json.load(open(cj, encoding="utf-8"))
        outdir = os.path.join(a.out, os.path.basename(folder_for(SHORTS, vid))) if a.out else folder_for(SHORTS, vid)
        src = None
        for v, n in jobs:
            if v != vid:
                continue
            if not 1 <= n <= len(clips):
                print(f"  clip {n}: not in clips.json (1-{len(clips)})", file=sys.stderr)
                continue
            if not a.force and glob.glob(os.path.join(outdir, f"{n:02}-*.mp4")):
                print(f"  clip {n}: already rendered, skipping (--force to redo)")
                continue  # resumable
            src = src or get_source(vid, a.source)
            print("Made", make_short(vid, n, clips[n - 1], src, outdir, pick_music(a.music), not a.no_cuts,
                                     not a.no_punch, a.hook_secs, a.progress_bar))


if __name__ == "__main__":
    main()
