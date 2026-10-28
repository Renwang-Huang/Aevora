FROM python:3.12.14-slim@sha256:44ff437bba879d4941b710a369a8f19266aea34b29002807f0c487fabc9eec9b
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOME=/home/aevora
WORKDIR /opt/aevora
COPY aevora_core /opt/aevora/aevora_core
COPY console /opt/aevora/console
COPY demo /opt/aevora/demo
RUN python -m pip install --no-cache-dir ./aevora_core ./console \
    && groupadd --gid 1000 aevora \
    && useradd --uid 1000 --gid 1000 --create-home --home-dir /home/aevora --shell /usr/sbin/nologin aevora \
    && chown -R 1000:1000 /home/aevora \
    && chmod 0700 /home/aevora
USER 1000:1000
ENTRYPOINT ["python", "-m", "aevora_observatory.server"]
CMD ["--replay-root", "/opt/aevora/demo", "--replay-sha256", "c460d927331db3e2b262c848337afd3bb5b93007538941c546827b895bd86776"]
