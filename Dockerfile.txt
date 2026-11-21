FROM python:3.12-slim

# ffmpeg is required for merging video+audio and for MP3 extraction
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg nodejs \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Render/Railway inject $PORT
CMD uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}
