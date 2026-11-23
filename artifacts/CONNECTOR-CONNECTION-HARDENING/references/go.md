# Go mechanics

The five properties from [SKILL.md](../SKILL.md), as they show up in the Go standard
library and the common client packages. Check the version the module actually pins:
defaults below are for current releases.

## Dialing

`net.Dialer` is the base for most clients. Its zero value has **no** connect
timeout and, in current Go releases, TCP keepalive **on** (15 seconds; a negative
`KeepAlive` turns it off).

TCP keepalive keeps an idle flow alive in a NAT table. It does not shorten the
fifteen-minute hang on a connection that is already dead: probes are sent only while
nothing is waiting to be acknowledged, so once a request is in flight, the kernel's
retransmission timeout decides. Only an operation deadline cuts that short.

```go
dialer := &net.Dialer{Timeout: 10 * time.Second}
conn, err := dialer.DialContext(ctx, "tcp", addr)
```

Use `DialContext`, not `Dial`. `Dial` cannot be cancelled, so a cancelled run still
waits out the timeout.

## SSH and SFTP (`golang.org/x/crypto/ssh`, `github.com/pkg/sftp`)

`ssh.ClientConfig.Timeout` bounds the **TCP connect only**. `ssh.Dial` then runs the
handshake with no deadline, and a server that accepts the TCP connection but never
completes the handshake hangs the caller. `ssh.Dial` also takes no context.

Dial yourself, bound the handshake with a deadline on the raw connection, then clear
it:

```go
conn, err := (&net.Dialer{Timeout: 10 * time.Second}).DialContext(ctx, "tcp", addr)
if err != nil {
	return nil, fmt.Errorf("dial %s: %w", addr, err)
}
if err := conn.SetDeadline(time.Now().Add(15 * time.Second)); err != nil {
	conn.Close()
	return nil, fmt.Errorf("set handshake deadline: %w", err)
}
c, chans, reqs, err := ssh.NewClientConn(conn, addr, config)
if err != nil {
	conn.Close()
	return nil, fmt.Errorf("ssh handshake with %s: %w", addr, err)
}
if err := conn.SetDeadline(time.Time{}); err != nil {
	c.Close()
	return nil, fmt.Errorf("clear handshake deadline: %w", err)
}
client := ssh.NewClient(c, chans, reqs)
```

SSH has its own keepalive, and the TCP keepalive underneath does not stand in for
it: a server's `ClientAliveInterval` or a proxy can end the session while TCP is
fine. Send the OpenSSH keepalive request on a ticker for as long as the client is
held, and stop the goroutine when the client closes:

```go
go func() {
	t := time.NewTicker(30 * time.Second)
	defer t.Stop()
	for {
		select {
		case <-done:
			return
		case <-t.C:
			if _, _, err := client.SendRequest("keepalive@openssh.com", true, nil); err != nil {
				return // the connection is gone; the next run's health check reconnects
			}
		}
	}
}()
```

`SendRequest` with `wantReply` set waits for the server's answer, and on a dead
connection that wait can itself hang, so the goroutine notices `done` only after it
returns. That is acceptable for a background keepalive, but do not call it on the
path of a run; check health there with an operation that has a deadline.

`pkg/sftp` operations take no context. To bound one, either set a deadline on the
underlying `net.Conn` around the call, or run it in a goroutine and close the client
when the context is done, which unblocks it with an error.

A cheap health check before reuse: `sftpClient.Getwd()` or a `Stat` of the working
directory.

## HTTP (`net/http`)

`http.DefaultClient` and a zero `http.Client` have **no timeout**. Set
`Client.Timeout` (it covers the whole exchange, including reading the body) or build
requests with `http.NewRequestWithContext` and a context deadline. For large
downloads where a whole-request timeout is wrong, bound the phases on the transport
instead:

```go
transport := http.DefaultTransport.(*http.Transport).Clone()
transport.DialContext = (&net.Dialer{Timeout: 10 * time.Second}).DialContext
transport.TLSHandshakeTimeout = 10 * time.Second
transport.ResponseHeaderTimeout = 30 * time.Second
transport.IdleConnTimeout = 90 * time.Second
```

Start from a clone of the default transport rather than a bare `&http.Transport{}`.
The bare struct drops the proxy settings from the environment and HTTP/2, and a
connector that worked through the corporate proxy stops working.

`IdleConnTimeout` is what keeps the transport's pool from reusing a connection a NAT
gateway has already forgotten. Set it below the shortest idle limit on the path.

Always drain and close the response body. An unread body keeps the connection out of
the pool, and the next request opens a new one.

## Databases (`database/sql`)

The pool retries on `driver.ErrBadConn`, but only if the driver reports a dead
connection that way, and only before any data was sent. Do not depend on it for
recovery. Configure the pool so it never hands out a connection that has sat idle
past the network's limit:

```go
db.SetConnMaxIdleTime(4 * time.Minute) // below the shortest idle limit on the path
db.SetConnMaxLifetime(30 * time.Minute)
```

Use the `...Context` methods (`QueryContext`, `ExecContext`, `PingContext`)
everywhere, so cancellation and deadlines reach the driver. `PingContext` at the start
of a run is the cheap health check.

## Contexts that are accepted and dropped

The pattern to grep for in review:

```go
func (c *Client) List(ctx context.Context, dir string) ([]os.FileInfo, error) {
	return c.sftp.ReadDir(dir) // ctx is never used
}
```

`go vet` does not catch it. revive's `unused-parameter` rule and `unparam` do, when
the project enables them; otherwise look for every function that takes a `ctx`
parameter and check that it is passed on, or that the function enforces it itself.
