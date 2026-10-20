FROM python:3.12.14-slim@sha256:44ff437bba879d4941b710a369a8f19266aea34b29002807f0c487fabc9eec9b
ARG AEVORA_UID=1000
ARG AEVORA_GID=1000
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOME=/home/aevora
WORKDIR /opt/aevora
COPY aevora_core /opt/aevora/aevora_core
COPY console /opt/aevora/console
COPY examples/observatory /opt/aevora/examples/observatory
RUN python -m pip install --no-cache-dir ./aevora_core ./console && mkdir -p /home/aevora /state && chmod 0700 /state && chown -R ${AEVORA_UID}:${AEVORA_GID} /home/aevora /state
USER ${AEVORA_UID}:${AEVORA_GID}
ENTRYPOINT ["python", "-m", "aevora_observatory.demo_server"]
