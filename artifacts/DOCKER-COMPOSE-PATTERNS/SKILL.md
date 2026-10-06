---
name: docker-compose-patterns
description: Writing and debugging compose.yaml for local data stacks - waiting for a database to be ready rather than started, keeping data in named volumes, secrets outside the file, development overrides.
---

# Docker Compose patterns

Compose describes how several containers run together. For a data project that is
usually a database, an orchestrator such as Airflow, and the job image that does the
work. Most Compose failures in that setting come from one gap: Compose knows whether
a container is *running*, and has no idea whether the program inside is *ready*.

## Wait for readiness, not for start

`depends_on` with no condition only orders container start. Postgres starts in a
second and accepts connections some seconds later, and in between the dependent
service connects, fails, and either crashes or, worse, retries into a half-initialised
database. The cure is a health check on the dependency and a condition on the
dependent:

```yaml
services:
  db:
    image: postgres:17
    environment:
      POSTGRES_USER: airflow
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD in .env}
      POSTGRES_DB: airflow
    volumes:
      - db-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U airflow -d airflow"]
      interval: 5s
      timeout: 3s
      retries: 5
      start_period: 10s

  airflow-init:
    image: apache/airflow:2.10.5
    command: db migrate
    environment: &airflow-env
      AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: postgresql+psycopg2://airflow:${POSTGRES_PASSWORD}@db/airflow
    depends_on:
      db:
        condition: service_healthy

  scheduler:
    image: apache/airflow:2.10.5
    command: scheduler
    environment: *airflow-env
    depends_on:
      airflow-init:
        condition: service_completed_successfully

volumes:
  db-data:
```

Three conditions exist and each has a use. `service_started` is the default and rarely
what you want for infrastructure. `service_healthy` waits for the health check and is
right for a database or broker. `service_completed_successfully` waits for a container
to exit with code 0, which is the correct shape for a migration or init job: the
scheduler must not start until the schema exists, and a one-shot container expresses
that without a sleep loop.

Every service named in a `service_healthy` condition needs a `healthcheck`; without one
Compose cannot evaluate the condition and reports an error. Use the service's own client
(`pg_isready`, `redis-cli ping`, `mysqladmin ping`) instead of probing a port, because an
open port does not mean the server has finished recovery or initialisation. Start from
`interval: 5s`, `timeout: 3s`, `retries: 5`, `start_period: 10s`. MySQL and RabbitMQ
take longer on first start, so give them 20 to 30 seconds of `start_period`, which is
the window in which failed checks are not counted against the retries.

## Data lives in named volumes

A container's filesystem is discarded with the container. A database writing to it
loses everything on `docker compose down` followed by `up`. Mount a named volume at
the database's data directory and declare it in the top-level `volumes:` key. Use bind
mounts for source code you want to edit live, and for nothing that must survive.

This is also why destructive commands deserve care here: the volume is the data. See
the last section.

## Secrets stay out of the file

`compose.yaml` is committed. A password written into it is in the history forever. Take
values from the environment, with a loud failure if one is missing:

```yaml
POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD in .env}
```

Compose reads a `.env` file next to `compose.yaml` automatically; keep it in `.gitignore`
and commit a `.env.example` with placeholders. A fallback such as `${DB_PASSWORD:-postgres}`
is acceptable for a throwaway local database where one-command startup matters, provided
it is plainly a development default and the port is not published beyond the machine.

Do not publish datastore ports to every interface. `"5432:5432"` makes the database
reachable from the network the laptop is on. Containers in the same Compose network reach
each other by service name without any published port; when a host tool such as a SQL
client needs access, publish to loopback only: `"127.0.0.1:5432:5432"`.

Do not mount the Docker socket into a service unless it genuinely manages containers.
Access to the socket is control of the host.

## Service definitions

- Pin image tags to a version: `postgres:17`, not `postgres:latest` and not a bare name.
  A floating tag turns "works on my machine" into "worked yesterday".
- Name the file `compose.yaml`. `docker-compose.yml` is the legacy name from the v1 tool.
- Leave `container_name` unset unless an external tool needs a fixed name; fixed names
  stop two copies of the stack from running side by side.
- `restart: unless-stopped` suits long-running infrastructure. A one-shot init job should
  not restart.
- Custom networks are only worth it when you need to isolate groups of services from each
  other. For one stack the default network is enough.

## Development overrides

Compose loads `compose.override.yaml` automatically on top of `compose.yaml`. Put what
differs for development there, such as bind mounts for source, debug ports and verbose
logging, and keep the base file close to what runs elsewhere. Overrides are merged, not
replaced, so the override only needs the keys that change.

For the edit-and-see loop prefer `develop.watch` to hand-written bind mounts. Use
`action: sync` for source files copied into the running container, `rebuild` for files
that change the image such as `requirements.txt`, and `sync+restart` for configuration
that needs the process restarted.

```yaml
services:
  pipeline:
    build: .
    develop:
      watch:
        - { action: sync, path: ./src, target: /app/src }
        - { action: rebuild, path: requirements.txt }
```

## Checking the file

```bash
docker compose config --quiet
```

This validates the file and resolves interpolation without printing it. A variable
written as `${NAME:?message}` makes it fail until the value exists, which is the point:
copy `.env.example` to `.env` first, and read that failure as the file working, not as
a broken file. Plain
`docker compose config` prints the resolved configuration, including every secret read
from `.env`, into your terminal and any log that captures it. Use `--quiet` by default.

## Commands that destroy data

`docker compose down -v` removes the named volumes, which means the database. `down`
alone removes containers and networks and leaves volumes. `docker compose rm -v` removes
anonymous volumes attached to the removed containers. Before any of these, say exactly
which volumes would go and what they hold, and get a yes. To reset only a stuck service,
`docker compose restart <service>` or `docker compose up -d --force-recreate <service>`
keeps the data. A volume declared `external: true` is not owned by the project and
`down -v` will not touch it; removing it is a standalone volume deletion and follows
`DOCKER-DESTRUCTIVE-GUARDRAILS`.

## Related

- A project with no Docker setup yet starts from `DOCKER-PROJECT-FOUNDATIONS`.
- How the images in the stack are built is `DOCKER-BUILD-STRATEGIES`.
