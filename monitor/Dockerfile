FROM python:3.11-slim

WORKDIR /app

COPY health_monitor.py .

EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=5s --retries=3 --start-period=5s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

CMD ["python", "health_monitor.py"]
