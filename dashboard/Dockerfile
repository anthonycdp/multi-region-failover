FROM python:3.11-slim

WORKDIR /app

COPY dashboard.py .

EXPOSE 3000

HEALTHCHECK --interval=10s --timeout=5s --retries=3 --start-period=5s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:3000/health')" || exit 1

CMD ["python", "dashboard.py"]
