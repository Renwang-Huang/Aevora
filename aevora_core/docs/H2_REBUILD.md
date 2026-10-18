# H2 clean rebuild

This is a maintainer procedure. The checkout includes private evaluator source;
never expose it, the database password, or this launcher to Participants.
Prerequisites are Linux user/PID namespaces, bubblewrap, Git, Docker Compose,
delegated cgroup memory/pids, uv and a Python 3.12 runtime with `os.pidfd_open`.

The ordinary Ubuntu 22.04 `/usr` and uv's standalone interpreter are insufficient
for this project's current native sandbox contracts. H2 retains their failed
regression attempts. No old assertion was relaxed. An independent Flatpak user
installation can reproduce the validated `/usr` layout without reading the
maintainer's installed runtime or virtual environment:

```sh
export FLATPAK_USER_DIR=/absolute/new/h2-flatpak
flatpak --user remote-add flathub https://flathub.org/repo/flathub.flatpakrepo
flatpak --user install --no-related --noninteractive -y flathub org.freedesktop.Platform//24.08
flatpak --user info --show-commit org.freedesktop.Platform//24.08
flatpak --user info --show-location org.freedesktop.Platform//24.08
```

Use the returned deployment's `files` directory as `--runtime-root`. Record the
actual download receipts, commit and interpreter hash. **24.08 is end of life**:
it preserves the H1 Python 3.12 baseline for reproducibility, and does not prove
an up-to-date hostile runtime. Upgrading the runtime without validating the
existing contracts is not part of this recipe.

Create dedicated host-only database secrets and a fresh service/volume:

```sh
python3 scripts/aevora_bootstrap.py /absolute/private/h2-secrets
AEVORA_H2_SECRET_DIR=/absolute/private/h2-secrets AEVORA_H2_PORT=17679 \
  docker compose -p unique-h2-project -f aevora_core/compose.h2.yaml up -d --wait
```

The Graph schema is initialized through the real official SDK. A minimal query
of an empty graph is valid; historical multihop evidence must first be imported
through the independently verified OrderFlow ingestion procedure if that
query is meant to demonstrate evidence traversal. Do not replace missing
history with fake outcomes or call an empty result a retrieved experience.

```sh
python3 aevora_core/scripts/rebuild_h2.py \
  --source-repository /absolute/h2-release-repository \
  --source-commit FULL_40_CHARACTER_COMMIT \
  --destination /absolute/new/clean-checkout \
  --evidence-directory /absolute/new/rebuild-evidence \
  --runtime-root /absolute/new/h2-flatpak/runtime/org.freedesktop.Platform/x86_64/24.08/COMMIT/files \
  --baseline-identities /absolute/h2-archive/g0/INHERITED_TEST_IDENTITIES.json \
  --database-port 17679 --graph aevora_h2_g0 \
  --password-file /absolute/private/h2-secrets/falkordb.password \
  --cgroup-parent /absolute/delegated/cgroup
```

The script clones the exact local release commit, creates a fresh venv,
downloads pinned dependencies from public PyPI without pip/uv cache, performs
a real authenticated query, and runs the developer suites. It checks actual
JUnit failures/errors/skips, duplicate identities and every inherited identity.
Each stage preserves argv/cwd/timestamps/exits/stdout/stderr hashes. Exit zero
without the final `REBUILD_RESULT.json` and identity gate is insufficient.

The runtime's acquisition and the service's creation remain explicit external
receipts, not facts the rebuild script can infer from a supplied directory.
The trusted launcher maps only the selected checkout, output directory, runtime,
tools, cgroups, resolver/certificates and host-only secret. It is a maintainer
launcher; the actual Candidate and Participant retain their narrower boundaries.
It uses an environment allowlist and never copies personal Codex credentials.
Public dependency acquisition requires ordinary network access. No model call
occurs in this rebuild. A completed historical Codex run cannot certify this
new source version's runtime integration.
