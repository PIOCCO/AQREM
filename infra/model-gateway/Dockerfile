FROM python:3.12-slim

WORKDIR /app
RUN groupadd --system --gid 1001 gw && useradd --system --uid 1001 --gid gw gw
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
USER gw
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health/live')"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--forwarded-allow-ips", "*"]
