# حمّلها (Hammilha) — Video Downloader

Paste a link from TikTok, Instagram, Facebook, YouTube, X and hundreds of other
sites, pick a quality, download without fuss. Arabic-first (RTL), mobile-first.

> **Change the app name in one line:** near the top of `app.py` you'll find
> `APP_NAME = "حمّلها"` — put any name between the quotes and the whole app
> (page title, header, everything) updates automatically.

## Tech

- **Backend:** Python + FastAPI + yt-dlp (ffmpeg for merging/MP3)
- **Frontend:** the whole page lives inside `app.py` (no templates folder, no
  build step)
- **Run:** Docker (recommended) or plain `uvicorn`

## The repo is only 4 files (on purpose)

```
app.py             ← backend + the whole web page inside it
requirements.txt   ← Python dependencies
Dockerfile         ← tells the host how to run it (Python + ffmpeg)
README.md          ← this file
```

Flat on purpose: you can create it entirely from your phone, no computer,
no git commands, no folders to upload.

## Deploy for free on Render — from your phone (step by step)

You need two free accounts, no credit card:

### Step 1 — GitHub account (free)
1. Open https://github.com in your phone browser → **Sign up**.
2. Confirm your email when GitHub emails you.

### Step 2 — Create the repository and add the 4 files
1. On GitHub, tap the **+** (top corner) → **New repository**.
2. Name: `hammilha` → Public → **Create repository**.
3. On the empty repo page tap **"creating a new file"**.
4. Name the file `app.py`, then copy-paste the full contents of `app.py`
   into the text box → scroll down → **Commit new file**.
5. Repeat for the other three files: `requirements.txt`, `Dockerfile`,
   `README.md` (same steps: + → new file → paste → commit).
   (If your browser allows it, **Add file → Upload files** also works for
   single files — but paste-and-commit works everywhere.)

### Step 3 — Render account (free)
1. Open https://render.com → **Get Started** → sign up **with GitHub**
   (this connects the two automatically).

### Step 4 — Deploy
1. In Render: **New → Web Service**.
2. Choose **"Build and deploy from a Git repository"** → pick your
   `hammilha` repo.
3. Render detects the **Dockerfile** automatically — leave all settings as
   they are.
4. Scroll down, pick the **Free** instance type → **Create Web Service**.
5. Wait about 5 minutes. When it says **Live**, tap the URL at the top
   (something like `https://hammilha.onrender.com`) — that's your app.

### Free-tier notes
- The app **sleeps after 15 minutes** with no visitors; the next visit takes
  ~30–60 seconds to wake up, then it's fast. Normal for the free plan.
- 750 free hours per month — enough to keep one app running 24/7.

### Alternative: Railway
https://railway.app → sign up with GitHub → **New Project → Deploy from
GitHub repo** → detects the Dockerfile automatically. The free trial credit
is one-time (~$5), so Render is the better long-term free option.

## Run on a computer (optional)

```bash
pip install -r requirements.txt
# ffmpeg must be installed (apt install ffmpeg / brew install ffmpeg)
uvicorn app:app --host 0.0.0.0 --port 8000
```

Open http://localhost:8000

## Known limitations (honest list)

- **YouTube** often blocks server/datacenter IPs with a "confirm you're not a
  bot" wall. Works on some networks, not others. Fix if needed: add cookies
  (yt-dlp `--cookies`) from a logged-in browser session.
- **Instagram** requires login for many posts; public reels sometimes work,
  private/login-walled ones don't without cookies.
- **TikTok** blocks some server IPs. `curl-cffi` impersonation is included,
  which helps, but a given host's IP may still be blocked.
- **Facebook** public videos work well (verified end-to-end in testing).
- "Without watermark": yt-dlp fetches the best source the platform serves;
  TikTok's official no-watermark streams aren't guaranteed — results vary by
  video.
