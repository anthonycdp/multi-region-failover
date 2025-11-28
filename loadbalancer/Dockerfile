FROM python:3.11-slim

WORKDIR /app

COPY failover_lb.py .

EXPOSE 9000

HEALTHCHECK --interval=10s --timeout=5s --retries=3 --start-period=5s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:9000/lb/health')" || exit 1

CMD ["python", "failover_lb.py"]
