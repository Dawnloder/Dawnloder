import os
import shutil
import tempfile
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp

app = FastAPI(title="Dawnloader API", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SECRETS_COOKIES_PATH = "/etc/secrets/cookies.txt"

def get_cookies_path():
    if not os.path.exists(SECRETS_COOKIES_PATH):
        return None
    writable_path = os.path.join(tempfile.gettempdir(), "yt_cookies.txt")
    try:
        if (os.path.exists(writable_path) and
            os.path.getsize(writable_path) == os.path.getsize(SECRETS_COOKIES_PATH) and
            os.path.getmtime(writable_path) >= os.path.getmtime(SECRETS_COOKIES_PATH)):
            return writable_path
    except OSError:
        pass
    try:
        shutil.copy(SECRETS_COOKIES_PATH, writable_path)
        os.chmod(writable_path, 0o600)
        return writable_path
    except Exception as e:
        print(f"[cookies] Copy fail: {e}")
        return None

def ydl_opts_base():
    opts = {
        'quiet': True,
        'no_warnings': False,
        'nocheckcertificate': True,
        'geo_bypass': True,
    }
    cookies = get_cookies_path()
    if cookies:
        opts['cookiefile'] = cookies
    return opts

@app.get("/")
def health():
    cookies = get_cookies_path()
    return {
        "status": "ok",
        "message": "Dawnloader API running v2.0",
        "cookies_loaded": cookies is not None
    }

@app.get("/api/thumbnail")
def get_thumbnail(url: str = Query(...)):
    try:
        opts = ydl_opts_base()
        opts['skip_download'] = True
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        return {"thumbnail": info.get('thumbnail')}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/formats")
def get_formats(url: str = Query(...)):
    try:
        opts = ydl_opts_base()
        opts['skip_download'] = True
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        formats = []
        for f in info.get('formats', []):
            # Skip formats jo playable nahi ne
            if f.get('vcodec') == 'none' and f.get('acodec') == 'none':
                continue
            formats.append({
                "format_id": f.get('format_id'),
                "ext": f.get('ext'),
                "resolution": f.get('resolution') or f.get('format_note'),
                "vcodec": f.get('vcodec'),
                "acodec": f.get('acodec'),
                "filesize": f.get('filesize') or f.get('filesize_approx'),
                "format_note": f.get('format_note'),
                "abr": f.get('abr'),
                "tbr": f.get('tbr'),
                "height": f.get('height'),
                "width": f.get('width'),
            })
        return {
            "title": info.get('title'),
            "uploader": info.get('uploader'),
            "duration": info.get('duration'),
            "thumbnail": info.get('thumbnail'),
            "formats": formats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/download")
def download(url: str = Query(...), format_id: str = Query(None), audio_only: bool = Query(False)):
    try:
        tmpdir = tempfile.mkdtemp()
        outtmpl = os.path.join(tmpdir, '%(title)s.%(ext)s')

        opts = ydl_opts_base()
        opts['outtmpl'] = outtmpl

        if audio_only:
            opts['format'] = 'bestaudio/best'
            opts['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}]
        elif format_id:
            # Format selection improved:
            # Agar specific format_id ditta, osnu use kar
            # Agar ohi na hove, taan best fallback
            opts['format'] = f'{format_id}+bestaudio/{format_id}/best'
        else:
            # Default: best video + best audio
            opts['format'] = 'bestvideo+bestaudio/best'

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        if not os.path.exists(filename):
            base, _ = os.path.splitext(filename)
            for ext in ['.mp3', '.mp4', '.webm', '.m4a', '.jpg', '.png', '.mkv']:
                if os.path.exists(base + ext):
                    filename = base + ext
                    break

        return FileResponse(filename, media_type='application/octet-stream', filename=os.path.basename(filename))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
