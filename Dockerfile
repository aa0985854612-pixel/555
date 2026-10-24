FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1
LABEL org.opencontainers.image.title="PigLedger" org.opencontainers.image.version="2.0.57"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIGLEDGER_DB=/data/pigledger.sqlite3
WORKDIR /app
RUN groupadd --gid 10001 pigledger && useradd --uid 10001 --gid 10001 --no-create-home pigledger && mkdir /data && chown pigledger:pigledger /data
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY --chown=pigledger:pigledger app /app/app
COPY VERSION /app/VERSION
USER pigledger
EXPOSE 8080
VOLUME /data
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/health',timeout=4)"
CMD ["python","-m","app.server","--host","0.0.0.0","--port","8080"]
