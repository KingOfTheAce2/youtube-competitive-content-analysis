"""Human-readable folder names for the clip tools: <date>_<title-slug>_<video id>."""
import glob
import os
import re
import sqlite3

DB = "./output/competitive_analysis.db"
_meta = None


def slug(text, n=60):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:n].strip("-")


def video_meta(vid):
    """(title, publish date) from the local database, or (None, None)."""
    global _meta
    if _meta is None:
        try:
            c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
            _meta = {v: (t, (d or "")[:10]) for v, t, d in c.execute("select video_id,title,publish_date from videos")}
        except Exception:
            _meta = {}
    return _meta.get(vid, (None, None))


def folder_for(root, vid):
    """Existing folder for this video under root (old bare-id names included), else the new readable path."""
    for d in glob.glob(os.path.join(root, f"*{vid}")):
        if os.path.isdir(d):
            return d
    title, date = video_meta(vid)
    name = f"{date}_{slug(title)}_{vid}" if title else vid
    return os.path.join(root, name)


def video_id_of(folder):
    return os.path.basename(folder.rstrip("/\\"))[-11:]
