FROM python:3.11-slim

WORKDIR /app

# No external dependencies needed - using stdlib only

COPY service.py .

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --retries=3 --start-period=5s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["python", "service.py"]
