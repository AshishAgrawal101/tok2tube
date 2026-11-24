"""Tok2Tube core: download your own TikTok posts without the watermark and upload them to YouTube as Shorts.

Everything personal lives in the data folder (see DATA below), never next to the code:
  client_secret.json   your Google OAuth "Desktop app" client (you download it from Google Cloud)
  token.json           your YouTube sign-in, written by sign_in()
  posted.json          TikTok id -> YouTube video, so nothing is posted twice
  downloads/           the downloaded videos and their info
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field

APP = "Tok2Tube"
DATA = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~/.config"), APP)
CLIENT = os.path.join(DATA, "client_secret.json")
TOKEN = os.path.join(DATA, "token.json")
POSTED = os.path.join(DATA, "posted.json")
SETTINGS = os.path.join(DATA, "settings.json")
DOWNLOADS = os.path.join(DATA, "downloads")
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]
SHORTS_MAX_SECONDS = 180

DEFAULT_SETTINGS = {
    "privacy": "private",          # private | unlisted | public
    "footer": "",                  # a line added to every description, e.g. "Play it free on Roblox."
    "add_shorts_tag": True,        # add #Shorts to the description
    "category": "20",              # YouTube category id (20 = Gaming, 22 = People & Blogs, 24 = Entertainment)
}


def ensure_data():
    os.makedirs(DOWNLOADS, exist_ok=True)


def _read_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _write_json(path, data):
    ensure_data()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def load_settings():
    s = dict(DEFAULT_SETTINGS)
    s.update(_read_json(SETTINGS, {}))
    return s


def save_settings(s):
    _write_json(SETTINGS, s)


def load_posted():
    return _read_json(POSTED, {})


def save_posted(p):
    _write_json(POSTED, p)


# ---------------------------------------------------------------- TikTok

@dataclass
class Video:
    id: str
    url: str
    file: str
    caption: str = ""
    hashtags: list = field(default_factory=list)
    uploader: str = ""
    date: str = ""
    duration: float = 0
    width: int = 0
    height: int = 0
    track: str = ""
    artist: str = ""
    thumbnail: str = ""
    watermarked: bool = False
    # the YouTube side, editable before upload
    title: str = ""
    description: str = ""
    tags: str = ""

    def warnings(self):
        w = []
        if self.watermarked:
            w.append("Only the watermarked copy was available.")
        if self.duration and self.duration > SHORTS_MAX_SECONDS:
            w.append(f"{int(self.duration)} s is over YouTube's 3 minute Shorts limit: it will be a normal video.")
        if self.width and self.height and self.width > self.height:
            w.append("Landscape video: YouTube will not treat it as a Short.")
        if self.track or self.artist:
            w.append(f"TikTok lists a sound ({self.artist or '?'} - {self.track or '?'}). "
                     "YouTube may claim or mute music from TikTok's library.")
        return w


def clean_url(url):
    url = url.strip()
    return url.split("?")[0] if "tiktok.com" in url else url


def fetch(url, progress=None) -> Video:
    """Download one TikTok (watermark-free when TikTok offers it). progress(fraction) is called while it runs."""
    import yt_dlp

    ensure_data()

    def hook(d):
        if progress and d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            if total:
                progress(min(1.0, d.get("downloaded_bytes", 0) / total))

    opts = {
        "outtmpl": os.path.join(DOWNLOADS, "%(id)s.%(ext)s"),
        # yt-dlp ranks TikTok's watermarked "download" format below the plain ones
        "format": "bv*+ba/b",
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "noprogress": True,
        "progress_hooks": [hook],
    }
    with yt_dlp.YoutubeDL(opts) as y:
        info = y.extract_info(clean_url(url), download=True)
        path = y.prepare_filename(info)
    if not path.endswith(".mp4"):
        path = os.path.splitext(path)[0] + ".mp4"
    chosen = info.get("requested_formats") or [info]
    marked = any("watermark" in str(f.get("format_note", "")).lower() or f.get("format_id") == "download"
                 for f in chosen)
    caption = (info.get("description") or info.get("title") or "").strip()
    v = Video(
        id=str(info.get("id")),
        url=info.get("webpage_url") or url,
        file=path,
        caption=caption,
        hashtags=re.findall(r"#(\w+)", caption),
        uploader=info.get("uploader") or "",
        date=info.get("upload_date") or "",
        duration=info.get("duration") or 0,
        width=info.get("width") or 0,
        height=info.get("height") or 0,
        track=info.get("track") or "",
        artist=info.get("artist") or "",
        thumbnail=info.get("thumbnail") or "",
        watermarked=marked,
    )
    fill_defaults(v, load_settings())
    _write_json(os.path.join(DOWNLOADS, f"{v.id}.json"), asdict(v))
    return v


def default_title(v: Video):
    first = next((ln for ln in v.caption.splitlines() if ln.strip()), "")
    t = re.sub(r"#\w+", "", first)
    t = re.sub(r"\s+", " ", t).strip(" -|")
    return (t or f"{v.uploader or 'New'} short")[:100]


def default_description(v: Video, settings):
    parts = [v.caption]
    footer = (settings.get("footer") or "").strip()
    if footer and footer.lower() not in v.caption.lower():
        parts.append(footer)
    if settings.get("add_shorts_tag", True) and "shorts" not in (h.lower() for h in v.hashtags):
        parts.append("#Shorts")
    return "\n\n".join(p for p in parts if p)[:5000]


def fill_defaults(v: Video, settings):
    v.title = v.title or default_title(v)
    v.description = v.description or default_description(v, settings)
    v.tags = v.tags or ", ".join(v.hashtags[:15])


# ---------------------------------------------------------------- YouTube

class NotSignedIn(Exception):
    pass


def _creds():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    c = Credentials.from_authorized_user_file(TOKEN, SCOPES) if os.path.exists(TOKEN) else None
    if c and c.expired and c.refresh_token:
        try:
            c.refresh(Request())
            with open(TOKEN, "w", encoding="utf-8") as f:
                f.write(c.to_json())
        except Exception as e:  # an expired test-mode token (7 days) or a revoked one
            raise NotSignedIn(f"Sign-in expired ({e.__class__.__name__}). Sign in again.") from e
    if not c or not c.valid:
        raise NotSignedIn("Not signed in to YouTube.")
    return c


def has_client():
    return os.path.exists(CLIENT)


def set_client(path):
    """Copy a downloaded OAuth client JSON into the data folder, checking it is a Desktop app client."""
    data = _read_json(path, None)
    if not isinstance(data, dict) or "installed" not in data:
        kind = ", ".join(data.keys()) if isinstance(data, dict) else "not JSON"
        raise ValueError(f"That file is not a Google 'Desktop app' OAuth client (found: {kind}).")
    _write_json(CLIENT, data)


def sign_in():
    from google_auth_oauthlib.flow import InstalledAppFlow

    if not has_client():
        raise NotSignedIn("Add your Google client file first (Settings).")
    ensure_data()
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT, SCOPES)
    c = flow.run_local_server(port=0, open_browser=True,
                              success_message="Tok2Tube is signed in. You can close this tab.")
    with open(TOKEN, "w", encoding="utf-8") as f:
        f.write(c.to_json())
    return channel()


def sign_out():
    if os.path.exists(TOKEN):
        os.remove(TOKEN)


def _yt():
    from googleapiclient.discovery import build

    return build("youtube", "v3", credentials=_creds(), cache_discovery=False)


def channel():
    """The signed-in channel's title, or raises NotSignedIn."""
    items = _yt().channels().list(part="snippet", mine=True).execute().get("items", [])
    return items[0]["snippet"]["title"] if items else "(no channel on this account)"


def upload(v: Video, privacy="private", publish_at=None, category="20", progress=None):
    """Upload a fetched video. Returns {"id", "url", "privacy"} and records it in posted.json."""
    from googleapiclient.http import MediaFileUpload

    if v.watermarked:
        raise ValueError("Refusing to upload: only the watermarked copy was downloaded.")
    tags = [t.strip().lstrip("#") for t in re.split(r"[,\n]", v.tags) if t.strip()]
    body = {
        "snippet": {"title": v.title[:100], "description": v.description[:5000], "categoryId": category,
                    "tags": tags[:30]},
        "status": {"privacyStatus": "private" if publish_at else privacy, "selfDeclaredMadeForKids": False},
    }
    if publish_at:
        body["status"]["publishAt"] = publish_at
    req = _yt().videos().insert(part="snippet,status", body=body,
                                media_body=MediaFileUpload(v.file, chunksize=4 * 1024 * 1024, resumable=True))
    resp = None
    while resp is None:
        status, resp = req.next_chunk()
        if status and progress:
            progress(status.progress())
    if progress:
        progress(1.0)
    res = {"id": resp["id"], "url": f"https://youtu.be/{resp['id']}", "privacy": body["status"]["privacyStatus"],
           "publishAt": publish_at}
    posted = load_posted()
    posted[v.id] = {**res, "tiktok": v.url, "title": v.title}
    save_posted(posted)
    return res


def already_posted(tiktok_id):
    return load_posted().get(tiktok_id)


def open_data_folder():
    ensure_data()
    if sys.platform == "win32":
        os.startfile(DATA)  # noqa: S606
    else:
        import subprocess

        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", DATA])
