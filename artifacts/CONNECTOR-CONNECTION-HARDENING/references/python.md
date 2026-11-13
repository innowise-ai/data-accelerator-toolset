# Python mechanics

The five properties from [SKILL.md](../SKILL.md), as they show up in the standard
library and the clients data connectors most often use. Python's defaults are less
forgiving than Go's: most clients have **no** timeout unless you pass one, and
sockets have TCP keepalive **off**.

## Sockets

`socket.create_connection(address, timeout=10)` bounds the connect, and the same
timeout then applies to every blocking call on that socket. Without it, the connect
is bounded only by the operating system (about two minutes on Linux) and a read on a
dead connection blocks until the kernel gives up on it.

TCP keepalive is off by default. Turn it on for a socket held across idle periods:

```python
sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
# these option names are Linux's; Windows and macOS have equivalents
# the defaults wait two hours before the first probe
sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 60)
sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 15)
sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 4)
```

The two-hour default first probe is why "keepalive is on" often protects nothing: the
NAT entry is gone long before the first probe is sent.

## HTTP (`requests`, `httpx`)

`requests` has **no default timeout**. Every call needs one, as a `(connect, read)`
pair:

```python
response = session.get(url, timeout=(10, 60))
```

The read value is the longest gap between bytes, not the whole download, so it is
already the "bound idle time between chunks" shape from SKILL.md.

`httpx` defaults to five seconds for everything, which is too short for some APIs
and is easy to override to `None` by accident. Set an explicit `httpx.Timeout`.

A `requests.Session` reuses pooled connections. The pool has no idle expiry, so after
a long idle period the first request can go to a dead connection. Mount an adapter
with retries for idempotent methods, or create the session per run.

## SSH and SFTP (`paramiko`)

`SSHClient.connect` has separate limits for each phase, and all of them matter:

```python
client.connect(
    host, port=22, username=user, pkey=key,
    timeout=10,          # TCP connect
    banner_timeout=15,   # server's SSH banner
    auth_timeout=15,     # authentication
)
client.get_transport().set_keepalive(30)
```

`timeout` alone leaves a server that accepts TCP and then stalls free to hang the
caller. `set_keepalive` sends SSH-level keepalives, which is what keeps a session
through a proxy or the server's own idle timeout.

SFTP channel operations block on the channel. Bound them with
`sftp.get_channel().settimeout(seconds)`.

## Databases (SQLAlchemy, psycopg)

Configure the pool so it validates or retires connections that have sat idle:

```python
engine = create_engine(
    url,
    pool_pre_ping=True,   # one cheap round trip on checkout; reconnects if dead
    pool_recycle=240,     # seconds; below the shortest idle limit on the path
    connect_args={"connect_timeout": 10},  # psycopg; other drivers name it differently
)
```

`pool_pre_ping` is property 1 done for you. Without it, the first query after an idle
period fails with an error that looks like a database problem.

## AWS SDK (`boto3`)

The defaults are a 60-second connect and a 60-second read timeout, with retries. They
are rarely wrong enough to cause a hang, but set them explicitly when the connector
runs inside a shorter orchestrator timeout:

```python
from botocore.config import Config
s3 = boto3.client("s3", config=Config(connect_timeout=10, read_timeout=60,
                                      retries={"max_attempts": 5, "mode": "standard"}))
```

## Cancellation

Synchronous Python has no cancellation token to forget. The equivalent defect is a
worker that ignores the orchestrator's stop signal while blocked in a call with no
timeout. Timeouts on every call are what make a stop take effect.

In asyncio, cancellation arrives as `CancelledError` at the next `await`. Wrap each
network call in `asyncio.timeout()` (3.11+) or `asyncio.wait_for()`, and do not
catch `CancelledError` without re-raising it: swallowing it is the asyncio form of
accepting a context and dropping it.
