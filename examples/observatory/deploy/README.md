# Local public image

This image contains only the independent public Core, Console and Hero Replay.
It does not contain the OrderFlow Runner, hidden Oracle, private repairs or host
credentials. The host owner runs the Core/API; an Agent receives a scoped MCP
channel only. Do not mount database secrets in an Agent container.

Build from the public source root (Linux AMD64, Python 3.12.14 pinned digest):

```sh
docker build -f examples/observatory/deploy/Dockerfile -t aevora-local:0.1.0 .
```

After the Quickstart's owned FalkorDB deployment, initialize using the actual
public CLI. This template assumes the owner UID is 1000, file mode 0600 and the
database is on host loopback. Other UID/platform arrangements need independent
validation. The read-only image runs as UID 1000 and receives only the one
host-owned secret file:

```sh
docker run --rm --network host --read-only --tmpfs /tmp:rw,nosuid,nodev \
  --mount "type=bind,src=$AEVORA_FALKORDB_PASSWORD_FILE,dst=/run/secrets/db,readonly" \
  --env AEVORA_FALKORDB_PASSWORD_FILE=/run/secrets/db \
  --env AEVORA_FALKORDB_HOST=127.0.0.1 \
  --env AEVORA_FALKORDB_PORT="$AEVORA_FALKORDB_PORT" \
  --env AEVORA_FALKORDB_GRAPH="$AEVORA_FALKORDB_GRAPH" \
  --entrypoint python aevora-local:0.1.0 -I -m aevora init

docker run --rm --network host --read-only --tmpfs /tmp:rw,nosuid,nodev \
  --mount "type=bind,src=$AEVORA_FALKORDB_PASSWORD_FILE,dst=/run/secrets/db,readonly" \
  --env AEVORA_FALKORDB_PASSWORD_FILE=/run/secrets/db \
  --env AEVORA_FALKORDB_HOST=127.0.0.1 \
  --env AEVORA_FALKORDB_PORT="$AEVORA_FALKORDB_PORT" \
  --env AEVORA_FALKORDB_GRAPH="$AEVORA_FALKORDB_GRAPH" \
  aevora-local:0.1.0
```

Open `http://127.0.0.1:17804`. New-volume LIVE correctly shows EMPTY. REPLAY
is the independent pinned historical product demonstration, never a substitute
for a failed LIVE read. Network-isolated Participant execution is a separate
Benchmark facility; this loopback owner API image is not a hostile Agent sandbox.
