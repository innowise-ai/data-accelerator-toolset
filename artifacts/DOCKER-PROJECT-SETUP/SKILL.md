---
name: docker-project-setup
description: Adding a first Docker setup to a Python data project - Dockerfile, compose.yaml and .dockerignore, with the database and other dependencies as Compose services instead of host installs. Use when a Python data project has no Docker setup yet and needs one.
---

# Docker project foundations

Use this when a project has no Docker setup, or an incomplete one, and the job is to
create the first working version. The aim is a project that builds and starts with one
command on a clean machine, with its dependencies running as containers. Tuning the
image or the stack comes afterwards and belongs to `DOCKER-IMAGE-BUILD` and
`DOCKER-COMPOSE-LOCAL-STACK`; a first scaffold that tries to be optimal is slower to write
and harder to review.

If the project already has a mature setup, or the person has said they do not want
Docker, this is the wrong artifact.

## Why dependencies run as containers

A data project needs a database more often than not: Postgres for Airflow metadata or
for a warehouse test double, Redis for a Celery broker, sometimes Kafka. Installing these
on the host works until two projects need different versions, or a new colleague spends
a day on setup, or the host install and the pipeline disagree about a locale or an
extension. A Compose service pins the version in a file that is reviewed with the code and
is removed by deleting the container. So when the project needs infrastructure, define it
as a Compose service from official images and configure it with environment variables;
do not tell the user to install it on their machine.

## The three files

Create all three together, at the project root, unless several services justify a `docker/`
directory.

**`.dockerignore` first**, so the very first build context is small and clean. It should
exclude `.git/`, virtual environments, `__pycache__/`, local data extracts, dbt `target/`
and `dbt_packages/`, and every credential file (`.env`, `pip.conf`, `.pypirc`, `.netrc`,
`profiles.yml` with real values, key files). The reasoning is in `DOCKER-IMAGE-BUILD`;
the point here is that the file must exist before anyone writes `COPY . .`.

**`Dockerfile`**, a working starter. For a Python project:

```dockerfile
# syntax=docker/dockerfile:1
FROM python:3.12-slim AS build
WORKDIR /app
RUN --mount=type=bind,source=requirements.txt,target=requirements.txt \
    --mount=type=cache,target=/root/.cache/pip \
    pip install --prefix=/install -r requirements.txt

FROM python:3.12-slim AS runtime
RUN useradd --system --uid 1001 appuser
COPY --from=build /install /usr/local
WORKDIR /app
COPY --chown=1001:1001 . .
USER 1001
ENTRYPOINT ["python", "-m", "pipeline"]
```

It is multi-stage so build tools do not ship, installs dependencies before copying source
so the cache survives code edits, and runs as a non-root user. Replace `pipeline` with the
project's entry point. If the project installs from a private index, the install step
needs a BuildKit secret rather than a copied `pip.conf`; do not paste the file in to make
the build pass.

**`compose.yaml`**, a local stack with the application and what it depends on:

```yaml
services:
  app:
    build: .
    environment:
      DATABASE_URL: postgresql://app:${POSTGRES_PASSWORD_URLENCODED:-dev-only-password}@db:5432/app
    depends_on:
      db:
        condition: service_healthy

  db:
    image: postgres:17
    environment:
      POSTGRES_USER: app
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-dev-only-password}
      POSTGRES_DB: app
    ports:
      - "127.0.0.1:5432:5432"
    volumes:
      - db-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app -d app"]
      interval: 5s
      timeout: 3s
      retries: 5

volumes:
  db-data:
```

The fallback password exists so a new colleague can start the stack with one command. It
is labelled as a development default, and the database port is published to loopback only,
so nothing off the machine can reach it. Document that `.env` overrides it, add `.env` to
`.gitignore`, and commit a `.env.example`. Why the health check and the `service_healthy`
condition matter is in `DOCKER-COMPOSE-LOCAL-STACK`.

When overriding the development password, set both `POSTGRES_PASSWORD` (raw) and
`POSTGRES_PASSWORD_URLENCODED` (for the URL) in `.env` and document both in
`.env.example`. Derive the encoded value with Python's
`urllib.parse.quote(raw_password, safe="")`: the synthetic `review@secret` becomes
`review%40secret`. Compose does not perform this encoding. Update both values
together; overriding only one leaves the application and database with different
passwords. Single-quote literal `.env` values containing `$`, and keep both
representations out of version control.

## Local versus production

Development favours speed of feedback: a bind mount or `develop.watch` for source, verbose
logs, ports on loopback. Production favours a small, fixed image: multi-stage build, source
copied in rather than mounted, resource limits. Keep one Dockerfile and select between them
with stages and `target:` rather than maintaining two files that drift apart.

## Done means it starts

A scaffold is not finished when the files exist. Run the build and the stack from a clean
state and confirm they come up:

```bash
docker compose config --quiet
docker compose up --build -d
docker compose ps
```

`config --quiet` validates the file without printing resolved values (plain `config` prints
secrets read from `.env`). `ps` should show the database as `healthy` and the application
running. Report what was not run, for example if Docker was not available to the agent, instead
of implying the setup was tested.

## Related

- Dockerfile detail, caching and credentials: `DOCKER-IMAGE-BUILD`.
- Stack wiring, readiness, volumes, overrides: `DOCKER-COMPOSE-LOCAL-STACK`.
- Anything that deletes containers, images or volumes: `DOCKER-DATA-LOSS-CONFIRMATION`.
