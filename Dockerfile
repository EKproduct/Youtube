FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl unzip \
    && rm -rf /var/lib/apt/lists/*

# yt-dlp needs a JavaScript runtime to decipher YouTube signatures; without one it
# falls back to JS-less extraction (deprecated) and many formats go missing, which
# surfaces downstream as "Requested format is not available". deno is yt-dlp's
# default enabled runtime.
RUN curl -fsSL https://deno.land/install.sh | DENO_INSTALL=/usr/local sh \
    && deno --version

WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

RUN useradd --create-home appuser \
    && mkdir -p /data/extracted_frames \
    && chown -R appuser:appuser /data
USER appuser

ENV OUTPUT_ROOT=/data/extracted_frames

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s CMD curl -f http://localhost:8000/healthz || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
