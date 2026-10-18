# Public release boundary

The release builder `tools/public_release.py` in the private maintainer repository
selects explicit product paths. The public package contains Core source/Schema v2/
Cypher, public tests/example, Console source/static assets, whitelisted historical
summary, h4 public evidence/verifier, deployment and public documentation.

The selection does not include OrderFlow app/benchmark/evaluator, hidden tests,
reference patches, maintainer implementations, root AGENTS, model sessions,
Host pins, full audit archives, .env, credentials, caches or Docker volumes.
Core's deferred legacy Host bridges are compatibility code only; the private
production authenticator and its pins are not shipped. Public synthetic fixtures
are scoped examples, not authority to publish production Outcomes.

PUBLIC_SELECTION.json in the release evidence lists every selected path and hash.
The independent Public staging Git starts with only those selected bytes; it does
not copy the maintainer Git history. Tree and complete proposed public history
are scanned separately. These checks are bounded release evidence and are not
a claim that no security defect exists.
