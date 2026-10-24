# scan-service — pure image work for in-house scanning (PR_in_house_scanning.md §7).
# Private Cloud Run service; the backend is its only invoker.
#
# No model weights: scan-v1.0 detects pages by contour (the DocAligner model was
# dropped from v1 by the spike's kill criterion, 2026-10-23), so the image needs
# nothing downloaded at build or at run time.
FROM python:3.11-slim

WORKDIR /srv

# opencv-python-headless needs libglib at import; nothing else is native.
RUN apt-get update && apt-get install -y --no-install-recommends libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY scan/ ./scan/

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/srv

EXPOSE 8080
# Cloud Run injects $PORT (8080 by default today; never assumed).
CMD exec uvicorn scan.api:app --host 0.0.0.0 --port ${PORT:-8080}
