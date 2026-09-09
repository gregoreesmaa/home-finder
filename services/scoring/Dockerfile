FROM python:3.12-slim
# Headless Chromium for the genuine-browser KV.ee fallback fetch (#77):
# kv.ee gates on the TLS fingerprint, which scripted HTTP cannot present.
RUN apt-get update \
    && apt-get install -y --no-install-recommends chromium \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
