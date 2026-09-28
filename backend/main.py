import os
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

COOKIES_PATH = "/etc/secrets/cookies.txt"

def ydl_opts_base():
    opts = {'quiet': True}
    if os.path.exists(COOKIES_PATH):
        opts['cookiefile'] = COOKIES_PATH
    return opts

@app.get("/")
def health():
    has_cookies = os.path.exists(COOKIES_PATH)
    return {
        "status": "ok",
        "message": "Dawnloader API running v2.0",
        "cookies_loaded": has_cookies
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
            if f.get('vcodec') != 'none' or f.get('acodec') != 'none':
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

        if audio_only:
            opts.update({
                'format': 'bestaudio/best',
                'outtmpl': outtmpl,
                'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}],
            })
        elif format_id:
            opts.update({'format': format_id, 'outtmpl': outtmpl})
        else:
            opts.update({'format': 'bestvideo+bestaudio/best', 'outtmpl': outtmpl})

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        if not os.path.exists(filename):
            base, _ = os.path.splitext(filename)
            for ext in ['.mp3', '.mp4', '.webm', '.m4a', '.jpg', '.png']:
                if os.path.exists(base + ext):
                    filename = base + ext
                    break

        return FileResponse(filename, media_type='application/octet-stream', filename=os.path.basename(filename))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
