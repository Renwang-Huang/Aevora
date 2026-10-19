# Order request handling after worker delay and restart

The service uses multiple independent OS worker processes sharing one persistent
SQLite database. Orders can be requested in two stages so a handler may prepare
work between claiming and completing an intent. A processing claim has a
deadline, may be renewed and may be replaced after expiry.

After delay, cancellation or a worker restart, operators have observed request
status and completion results that do not correspond to the intended order and
inventory state. Ordinary uninterrupted requests usually work. Investigate the
public code and processing records, implement a repair and add useful public
regressions. Preserve the existing APIs, service capacity and concurrent 2/4
worker deployment.

Read public.json/TASK.md and the public request-module docstrings for complete
API, persistence and Clock contracts. Run the independent local public checks
with `python tests/public/test_episode_d_v02.py`. Its diagnostic NOW server owns
only that local test's time; it cannot modify the deployment's shared authority.

Retries must retain request payload and discover one durable result. Claiming
does not reserve inventory. An unfinished intent confirmed cancelled cannot
later publish an order through its old handle. Completed-first cancellation
returns ALREADY_COMPLETED and the original result. Insufficient capacity keeps a
PENDING intent available for retry and must not remove an existing legitimate
order. A matching cancelled order is discovered without reserving it again.

Support normal SQLite DELETE/WAL modes and distinguish business results from
Clock, transport and database failures. Do not disable takeover/concurrency,
reject otherwise valid traffic, change test requirements, fabricate data or
delete persistent audit history to avoid the incident. Submit business Python
changes under app/; public tests are preserved separately.
