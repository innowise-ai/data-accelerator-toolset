---
name: docker-image-build
description: Writing and reviewing Dockerfiles for Python data images - keeping credentials out of layers, build cache order, multi-stage builds, running as non-root. Use when writing, reviewing or speeding up a Dockerfile for a data workload.
---

# Docker build strategies

An image is a stack of layers, and every layer is stored whole. That one fact
explains most of what goes wrong in a Dockerfile: a file added in one layer and
deleted in the next is still in the image, a changed line early in the file
invalidates the cache for everything after it, and anything that touched a
credential leaves a copy of it behind. The rules below are consequences of that,
so when a case is not listed, ask what each layer will contain.

## Credentials never enter a layer

A data image needs credentials more often than a web image does: a private PyPI
index to install the team's shared package, a warehouse key for dbt, a deploy key
to clone a private repository. Each of the usual ways of supplying them leaves a
copy in the image.

- **`ARG` and `ENV`** are recorded in the image metadata. `docker history` prints
  them to anyone who can pull the image.
- **`COPY` of a credential file** (`pip.conf`, `.pypirc`, `.netrc`, a
  service-account JSON, `~/.aws/credentials`, a `.env`, an SSH key) puts the file
  in a layer. Deleting it in a later `RUN` hides it from the running container but
  not from the layer, and it also sits in the build cache.
- **A `profiles.yml` with a real password** is the same case. dbt images are the
  place this happens most, because the profile has to exist somewhere at runtime.
  Bake in a profile that reads `{{ env_var('DBT_PASSWORD') }}` and pass the value
  when the container starts, not when the image is built.

BuildKit secrets exist for the build-time case. The secret is mounted for a single
`RUN` and is not written to any layer:

```dockerfile
# syntax=docker/dockerfile:1
RUN --mount=type=secret,id=pipconf,target=/etc/pip.conf \
    --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt
```

```bash
docker buildx build --secret id=pipconf,src=$HOME/.config/pip/pip.conf .
```

Use `required=true` on the mount when the build cannot succeed without the
credential, so a forgotten `--secret` fails immediately instead of falling back to
the public index and installing something different. Do not `echo` the secret or
substitute it into a command line: build logs with `--progress=plain` print the
expanded command.

For a private Git dependency use `--mount=type=ssh` and populate `known_hosts`
inside the same `RUN`. Do not turn off host-key checking to make the step pass:
that removes the only thing stopping the build from cloning from an impostor.
`ssh-add -l` lists every key the step can use, so check that the agent holds only
the key this build needs.

Add the credential files to `.dockerignore` as well, but treat that as a second
line of defence. It protects against a broad `COPY . .`; it does not protect a file
you meant to use.

## Order the Dockerfile by how often things change

The cache is keyed on the instruction and the files it reads, in order. Anything
after a changed layer is rebuilt. Dependencies change rarely and source changes on
every commit, so install dependencies first:

```dockerfile
# syntax=docker/dockerfile:1
FROM python:3.12-slim AS build
WORKDIR /app
RUN --mount=type=bind,source=requirements.txt,target=requirements.txt \
    --mount=type=cache,target=/root/.cache/pip \
    pip install --prefix=/install -r requirements.txt
COPY . .
```

Binding `requirements.txt` into the install step, rather than copying it, keeps the
manifest out of a layer and still invalidates the step when it changes. This is
safe because `pip install -r` only reads the file. If a step writes the manifest
back, copy it instead.

The pip cache mount keeps downloaded wheels between builds without putting them in
the image, so there is no `--no-cache-dir` and no cleanup step to remember.

Pin the base image to a version, for example `python:3.12-slim`, and to a digest
where reproducibility matters. `latest` moves under you: a build that worked last
week fails after the base image changes its Python or its OS libraries, and nothing
in your repository changed.

## Separate the build from the run

Compilers and headers are needed to build wheels like `psycopg2` or `pyarrow` from
source, and not needed to run them. A multi-stage build compiles in one stage and
copies only the result into the runtime stage:

```dockerfile
FROM python:3.12-slim AS runtime
COPY --from=build /install /usr/local
COPY --from=build --chown=1001:1001 /app /app
RUN useradd --system --uid 1001 appuser
USER 1001
WORKDIR /app
ENTRYPOINT ["python", "-m", "pipeline"]
```

Name every stage so `COPY --from=build` reads as intent and `--target` can pick a
stage. Prefer a `slim` variant over `alpine` for Python unless you have checked your
dependencies: Alpine uses musl, and a package that publishes prebuilt wheels only for
glibc is compiled from source there, which makes the build slower and often the image
no smaller. Check with `pip download --only-binary=:all:` before committing to Alpine.

## Run as a non-root user

A process running as root inside a container is root on anything it can reach: a
mounted volume, a bind-mounted source tree, the Docker socket if it was mounted. A
pipeline that only reads and writes its own directory has no use for that. Create the
user in the runtime stage and set `USER` after the last file operation.

Use the numeric uid in `--chown` when the copy uses `--link`. A linked copy is its own
layer and cannot see users created by earlier `RUN` steps, so a name resolves to
nothing.

## `.dockerignore` and the build context

The context is everything sent to the builder. Exclude `.git/`, virtual environments,
`__pycache__/`, local data extracts, dbt `target/` and `dbt_packages/`, notebooks'
checkpoints, and every credential file. A multi-gigabyte sample dataset in the
project folder makes every build slow even when nothing copies it, because it is
uploaded first.

## Checking the result

```bash
docker build -t pipeline-check .
docker image inspect pipeline-check --format '{{.Config.User}} {{.Size}}'
docker history --no-trunc pipeline-check
```

`docker history` shows build instructions, not the contents of copied files. A
clean history does not prove that credentials are absent: `COPY . .` can include a
password without showing its value in the history. Inspect the image configuration
as well, including environment variables, and check the contents of every image
layer with a tool that scans all layers for secrets. Alternatively, use
`docker image save --output <archive-path> pipeline-check` to save the image in a
private temporary directory and inspect each layer archive, decompressing it as
needed. Include files deleted or overwritten by later layers; inspecting only a
running container or a flattened filesystem misses them.

Keep any archive and inspection output containing credentials out of the repository
and shared logs. Report which checks ran and their limits; neither a clean history
nor a scanner's lack of findings guarantees that an image contains no secrets.
Also confirm that the configured user is non-root and that the image size is
reasonable for its dependencies.

## Related

- A project with no Docker setup yet starts from `DOCKER-PROJECT-SETUP`.
- Wiring the image into a stack with a database is `DOCKER-COMPOSE-LOCAL-STACK`.
- Anything that removes images, containers or volumes goes through
  `DOCKER-DATA-LOSS-CONFIRMATION`.
