# -*- coding: utf-8 -*-
"""
حمّلها - Video downloader web app (v1)
FastAPI + yt-dlp. Single-page Arabic (RTL) frontend.

Run locally:
    pip install -r requirements.txt
    uvicorn app:app --host 0.0.0.0 --port 8000
"""

import os
import re
import uuid
import shutil
import tempfile
import threading

import yt_dlp
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel
from starlette.background import BackgroundTask

# ---------------------------------------------------------------- config ----
# Change the app name in ONE place (also mirrored in templates/index.html).
APP_NAME = "حمّلها"

DOWNLOAD_DIR = tempfile.mkdtemp(prefix="hammilha_")
MAX_FILE_AGE_SECONDS = 30 * 60  # temp files are deleted after 30 minutes

app = FastAPI(title=APP_NAME)


class FetchRequest(BaseModel):
    url: str


# ------------------------------------------------------------- yt-dlp -------
YDL_BASE_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "noplaylist": True,
    "noprogress": True,
    "socket_timeout": 20,"format_sort": ["codec:avc:m4a", "res", "fps", "br"],
}


def extract_info(url: str):
    opts = dict(YDL_BASE_OPTS)
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)


def pick_qualities(info):
    """Decide which quality buttons to show, based on real formats."""
    heights = set()
    for f in info.get("formats") or []:
        h = f.get("height")
        if h:
            heights.add(int(h))

    qualities = [{"id": "best", "label": "أفضل جودة", "sub": "أعلى دقة متاحة"}]
    for h in (1080, 720, 480, 360):
        if any(x >= h for x in heights):
            qualities.append(
                {"id": f"p{h}", "label": f"{h}p", "sub": "جودة " + ("عالية" if h >= 720 else "متوسطة")}
            )
    qualities.append({"id": "audio", "label": "صوت فقط (MP3)", "sub": "للأغاني والمقاطع الصوتية"})
    return qualities


QUALITY_FORMATS = {
    "best": "bv*+ba/b",
    "p1080": "bv*[height<=1080]+ba/b[height<=1080]/b",
    "p720": "bv*[height<=720]+ba/b[height<=720]/b",
    "p480": "bv*[height<=480]+ba/b[height<=480]/b",
    "p360": "bv*[height<=360]+ba/b[height<=360]/b",
    "audio": "ba/b",
}


def sanitize_filename(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|]+', "", name).strip()
    return name[:80] or "video"


# ------------------------------------------------------------- cleanup ------
def cleanup_old_files():
    now = __import__("time").time()
    for fname in os.listdir(DOWNLOAD_DIR):
        path = os.path.join(DOWNLOAD_DIR, fname)
        try:
            if now - os.path.getmtime(path) > MAX_FILE_AGE_SECONDS:
                os.remove(path)
        except OSError:
            pass


def start_cleaner():
    def loop():
        import time
        while True:
            time.sleep(600)
            cleanup_old_files()

    t = threading.Thread(target=loop, daemon=True)
    t.start()


start_cleaner()


# ------------------------------------------------------------- routes -------
@app.get("/", response_class=HTMLResponse)
def index():
    return INDEX_HTML.replace("__APP_NAME__", APP_NAME)


@app.post("/api/info")
def api_info(req: FetchRequest):
    url = req.url.strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="الرابط غير صحيح")
    try:
        info = extract_info(url)
    except yt_dlp.utils.DownloadError:
        raise HTTPException(
            status_code=400,
            detail="مقدرش أقرا الفيديو من الرابط ده. اتأكد إن الرابط صحيح والفيديو عام (مش خاص).",
        )
    except Exception:
        raise HTTPException(status_code=500, detail="حصل خطأ غير متوقع. جرب تاني.")

    return {
        "title": info.get("title") or "فيديو",
        "thumbnail": info.get("thumbnail"),
        "duration": info.get("duration"),
        "uploader": info.get("uploader") or info.get("channel"),
        "site": info.get("extractor_key"),
        "qualities": pick_qualities(info),
    }


@app.get("/api/download")
def api_download(url: str, quality: str = "best"):
    fmt = QUALITY_FORMATS.get(quality, QUALITY_FORMATS["best"])
    job_id = uuid.uuid4().hex[:10]
    outtmpl = os.path.join(DOWNLOAD_DIR, f"{job_id}.%(ext)s")

    opts = dict(YDL_BASE_OPTS)
    opts.update(
        {
            "format": fmt,
            "outtmpl": outtmpl,
            "merge_output_format": "mp4",
        }
    )
    if quality == "audio":
        opts["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ]

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except yt_dlp.utils.DownloadError:
        raise HTTPException(status_code=400, detail="التحميل فشل. جرب جودة تانية أو اتأكد من الرابط.")
    except Exception:
        raise HTTPException(status_code=500, detail="حصل خطأ أثناء التحميل. جرب تاني.")

    # find the produced file
    produced = [f for f in os.listdir(DOWNLOAD_DIR) if f.startswith(job_id)]
    if not produced:
        raise HTTPException(status_code=500, detail="الملف مش موجود بعد التحميل.")
    path = os.path.join(DOWNLOAD_DIR, produced[0])
    ext = produced[0].split(".", 1)[1]
    filename = sanitize_filename(info.get("title") or "video") + "." + ext

    media_type = "audio/mpeg" if ext == "mp3" else "video/mp4"
    return FileResponse(
        path,
        media_type=media_type,
        filename=filename,
        background=BackgroundTask(lambda p=path: os.path.exists(p) and os.remove(p)),
    )


@app.get("/api/health")
def health():
    return {"ok": True, "name": APP_NAME}


@app.exception_handler(404)
def not_found(request, exc):
    return JSONResponse({"detail": "الصفحة مش موجودة"}, status_code=404)


# --------------------------------------------------------- frontend ------
# The entire page lives here so the repo stays flat (phone-friendly upload).
INDEX_HTML = r"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<title>__APP_NAME__ — حمّل أي فيديو</title>
<style>
  :root{
    --bg:#0f1220; --card:#191d31; --card2:#20253d;
    --accent:#6c5ce7; --accent2:#00cec9; --text:#f2f3fa; --muted:#9aa0b8;
    --radius:18px;
  }
  *{box-sizing:border-box; margin:0; padding:0; -webkit-tap-highlight-color:transparent}
  body{
    font-family:"Segoe UI", Tahoma, "Noto Kufi Arabic", system-ui, sans-serif;
    background:linear-gradient(160deg,#0f1220 0%,#171a2e 60%,#101527 100%);
    color:var(--text); min-height:100vh; display:flex; flex-direction:column; align-items:center;
    padding:24px 16px 60px;
  }
  .wrap{width:100%; max-width:520px}
  header{text-align:center; margin:24px 0 28px}
  .logo{font-size:44px; font-weight:800; background:linear-gradient(90deg,var(--accent),var(--accent2));
    -webkit-background-clip:text; background-clip:text; color:transparent}
  .tagline{color:var(--muted); margin-top:8px; font-size:15px}
  .card{background:var(--card); border-radius:var(--radius); padding:18px; box-shadow:0 10px 30px rgba(0,0,0,.35)}
  .input-row{display:flex; gap:8px}
  input[type=url]{
    flex:1; background:var(--card2); border:1.5px solid #2c3252; color:var(--text);
    border-radius:12px; padding:14px; font-size:16px; outline:none; direction:ltr; text-align:left;
  }
  input[type=url]:focus{border-color:var(--accent)}
  button{
    border:none; cursor:pointer; border-radius:12px; font-size:16px; font-weight:700;
    font-family:inherit; transition:transform .05s ease, opacity .2s;
  }
  button:active{transform:scale(.97)}
  .btn-main{background:linear-gradient(90deg,var(--accent),#8e7bff); color:#fff; padding:14px 20px}
  .btn-full{width:100%; padding:16px; margin-top:14px}
  .hint{color:var(--muted); font-size:13px; margin-top:12px; text-align:center; line-height:1.7}
  .hidden{display:none !important}
  /* video card */
  #videoCard{margin-top:18px; overflow:hidden}
  .thumb-wrap{position:relative; border-radius:12px; overflow:hidden}
  #thumb{width:100%; display:block; max-height:260px; object-fit:cover}
  #duration{position:absolute; bottom:8px; left:8px; background:rgba(0,0,0,.7); padding:3px 10px;
    border-radius:8px; font-size:13px}
  #vtitle{font-size:16px; font-weight:700; margin:12px 0 4px; line-height:1.5}
  #vmeta{color:var(--muted); font-size:13px; margin-bottom:14px}
  .q-grid{display:grid; grid-template-columns:1fr 1fr; gap:10px}
  .q-btn{background:var(--card2); color:var(--text); padding:14px 8px; border:1.5px solid #2c3252; text-align:center}
  .q-btn small{display:block; color:var(--muted); font-weight:400; font-size:12px; margin-top:3px}
  .q-btn.selected{border-color:var(--accent2); background:#1d3242}
  /* spinner */
  .spinner{width:22px; height:22px; border:3px solid rgba(255,255,255,.25); border-top-color:#fff;
    border-radius:50%; animation:spin .8s linear infinite; display:inline-block; vertical-align:middle}
  @keyframes spin{to{transform:rotate(360deg)}}
  #status{text-align:center; margin-top:14px; font-size:14px; min-height:20px}
  #status.error{color:#ff7675}
  #status.ok{color:var(--accent2)}
  footer{margin-top:36px; color:var(--muted); font-size:12px; text-align:center; line-height:1.8}
  .supported{display:flex; flex-wrap:wrap; gap:8px; justify-content:center; margin-top:16px}
  .chip{background:var(--card2); color:var(--muted); font-size:12px; padding:5px 12px; border-radius:999px}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="logo">__APP_NAME__</div>
    <div class="tagline">حمّل أي فيديو من السوشيال ميديا في ثواني 🎬</div>
  </header>

  <div class="card">
    <div class="input-row">
      <input type="url" id="urlInput" placeholder="الصق رابط الفيديو هنا..." inputmode="url" autocomplete="off">
      <button class="btn-main" id="fetchBtn">جلب</button>
    </div>
    <div class="hint">انسخ رابط الفيديو من تيك توك، انستجرام، فيسبوك، يوتيوب... والصقه فوق</div>
  </div>

  <div id="status"></div>

  <div class="card hidden" id="videoCard">
    <div class="thumb-wrap">
      <img id="thumb" alt="">
      <span id="duration"></span>
    </div>
    <div id="vtitle"></div>
    <div id="vmeta"></div>
    <div class="q-grid" id="qGrid"></div>
    <button class="btn-main btn-full hidden" id="downloadBtn">⬇️ تحميل</button>
  </div>

  <div class="supported">
    <span class="chip">تيك توك</span><span class="chip">انستجرام</span><span class="chip">فيسبوك</span>
    <span class="chip">يوتيوب</span><span class="chip">تويتر / X</span><span class="chip">+ مئات المواقع</span>
  </div>

  <footer>
    حمّل الفيديوهات للاستخدام الشخصي فقط. احترم حقوق صناع المحتوى 💜
  </footer>
</div>

<script>
const urlInput = document.getElementById('urlInput');
const fetchBtn = document.getElementById('fetchBtn');
const status = document.getElementById('status');
const videoCard = document.getElementById('videoCard');
const qGrid = document.getElementById('qGrid');
const downloadBtn = document.getElementById('downloadBtn');
let selectedQuality = 'best';
let currentUrl = '';

function setStatus(msg, cls){
  status.textContent = msg || '';
  status.className = cls || '';
}
function setLoading(on, btn, label){
  btn.disabled = on;
  btn.innerHTML = on ? '<span class="spinner"></span>' : label;
}
function fmtDuration(s){
  if(!s) return '';
  const m = Math.floor(s/60), sec = Math.floor(s%60);
  return (m? m+':' : '0:') + String(sec).padStart(2,'0');
}

// paste from clipboard on focus (mobile convenience, best-effort)
urlInput.addEventListener('focus', async () => {
  if(urlInput.value) return;
  try{
    const t = await navigator.clipboard.readText();
    if(t && /^https?:\/\//.test(t.trim())) urlInput.value = t.trim();
  }catch(e){ /* clipboard permission denied: fine */ }
});

fetchBtn.addEventListener('click', fetchInfo);
urlInput.addEventListener('keydown', e => { if(e.key === 'Enter') fetchInfo(); });

async function fetchInfo(){
  const url = urlInput.value.trim();
  if(!/^https?:\/\//.test(url)){ setStatus('الصق رابط صحيح الأول 🙏','error'); return; }
  currentUrl = url;
  videoCard.classList.add('hidden');
  downloadBtn.classList.add('hidden');
  setLoading(true, fetchBtn, 'جلب');
  setStatus('بنجيب معلومات الفيديو...');
  try{
    const res = await fetch('/api/info', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({url})
    });
    const data = await res.json();
    if(!res.ok){ setStatus(data.detail || 'حصل خطأ','error'); return; }
    document.getElementById('vtitle').textContent = data.title;
    document.getElementById('vmeta').textContent =
      [data.uploader, data.site].filter(Boolean).join(' • ');
    const img = document.getElementById('thumb');
    if(data.thumbnail){ img.src = data.thumbnail; img.style.display='block'; }
    else { img.style.display='none'; }
    document.getElementById('duration').textContent = fmtDuration(data.duration);
    renderQualities(data.qualities);
    videoCard.classList.remove('hidden');
    setStatus('اختار الجودة واضغط تحميل 👇','ok');
  }catch(e){
    setStatus('مفيش اتصال بالسيرفر. جرب تاني.','error');
  }finally{
    setLoading(false, fetchBtn, 'جلب');
  }
}

function renderQualities(qualities){
  qGrid.innerHTML = '';
  selectedQuality = qualities[0].id;
  qualities.forEach(q => {
    const b = document.createElement('button');
    b.className = 'q-btn' + (q.id === selectedQuality ? ' selected' : '');
    b.innerHTML = q.label + (q.sub ? '<small>'+q.sub+'</small>' : '');
    b.onclick = () => {
      selectedQuality = q.id;
      qGrid.querySelectorAll('.q-btn').forEach(x => x.classList.remove('selected'));
      b.classList.add('selected');
      downloadBtn.classList.remove('hidden');
    };
    qGrid.appendChild(b);
  });
  downloadBtn.classList.remove('hidden');
}

downloadBtn.addEventListener('click', () => {
  setStatus('جاري التحميل... الفيديو هينزل لوحده خلال ثواني ⏳');
  const a = document.createElement('a');
  a.href = '/api/download?url=' + encodeURIComponent(currentUrl) + '&quality=' + encodeURIComponent(selectedQuality);
  a.download = '';
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => setStatus('لو التحميل مبدأش، اضغط الزر تاني.'), 8000);
});
</script>
</body>
</html>
"""
