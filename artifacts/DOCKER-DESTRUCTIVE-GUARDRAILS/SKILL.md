---
name: docker-destructive-guardrails
description: Before running or recommending any Docker command that deletes containers, images, networks, build cache or volumes - say what will be lost and get a yes first, and prefer a narrower command.
---

# Docker destructive-command guardrails

Docker makes deletion cheap and recovery impossible. `docker volume rm` does not
move data to a bin; the volume and everything in it are gone, and for a data project
the volume is frequently the database. This skill exists because the commands that
destroy data are usually offered as the fix for something else: disk is full, a
container is stuck, a build behaves oddly, the user said "start fresh".

The rule is one sentence: **before running a destructive command, state exactly what
will be lost, and wait for an explicit yes.** The rest is working out what "exactly
what" means for each command, and finding a narrower command that solves the actual
problem.

## Why "clean up" is not consent

A request such as "clean up Docker", "wipe it and start over" or "free some space" names
a goal, not a command. The widest command that reaches the goal is rarely the one the
person has in mind, and they cannot weigh a loss they have not been shown. So translate
the request into a concrete command, show what it removes, and ask. Disk pressure almost
always has a narrower fix than `docker system prune -a --volumes`; start with
`docker system df`, which shows what is using space, by category, without changing
anything.

## What each command takes with it

| Command | Removes | Narrower alternative |
|---|---|---|
| `docker rm <c>` | A stopped container and its writable layer | Already narrow; fine for one named, stopped container |
| `docker rm -f <c>` | The same, after killing a running container without graceful shutdown | `docker stop <c>` first, then `docker rm` |
| `docker rm -f -v <c>` | The above plus the container's anonymous volumes | Drop `-v` unless you have checked the volumes |
| `docker kill <c>` | Nothing removed, but the process dies with no grace period, so unflushed writes are lost | `docker stop <c>` |
| `docker container prune` | Every stopped container on the host, not only yours | Remove the named ones with `docker rm` |
| `docker system prune` | Stopped containers, unused networks, dangling images, build cache | Prune the one category that is the problem |
| `docker system prune -a` | The above plus every image no container uses, including ones you pulled on purpose | `docker image prune` without `-a` |
| `docker system prune --volumes` | The above plus unused *anonymous* volumes | Do not add `--volumes` until you have listed them |
| `docker rmi` / `docker image rm` | One image; `-f` overrides the checks that protect a tagged or referenced image | Run without `-f` first |
| `docker image prune -a` | Every image not used by a container | `docker image prune` for dangling only |
| `docker network rm` / `prune` | One network, or every network with no containers attached | Remove by name |
| `docker builder prune [-a]` | Build cache; `-a` also removes helper images and shared cache, forcing a cold rebuild | Plain `docker builder prune` |
| `docker buildx rm` | A builder instance (not the cache) | Check which builder is in use first |
| `docker context rm` | The local connection settings for a Docker host; not the remote resources, but not trivial to recreate | Check `docker context ls` |
| `docker volume rm` / `prune` | The volume and its data, permanently; `prune -a` widens from anonymous to named volumes | Inspect first with `docker volume ls` and `docker volume inspect` |

Named volumes are not touched by `docker system prune`, even with `--volumes`; only
anonymous ones are. A named volume is deleted only by an explicit `docker volume rm`,
`docker volume prune -a`, or `docker compose down -v`. That is a useful thing to tell
the user, because "will my database survive" is the question they actually have.

Compose has its own destructive forms, covered in `DOCKER-COMPOSE-PATTERNS`:
`docker compose down -v` and `docker compose rm -v`.

## When to proceed without asking

Asking before every `docker rm` makes the rule easy to ignore, so the low-risk cases are
carved out. The agent may remove a container without a blocking confirmation when **all**
of these hold:

- it is one specific, identified container, not a sweep;
- it is already stopped, or the agent created and started it earlier in this session
  purely for testing or debugging;
- nothing unpersisted is known to be at risk;
- the user asked for this in this session, not the agent's own initiative.

Then remove it and say what was removed. Stopping such a container with `docker stop` is
treated the same way. Anything else, including `docker kill`, every prune, and any
container the agent did not create, needs the confirmation described above.

## Writing the confirmation

A good confirmation names the objects, not the command. The numbers below are
illustrative; take the real ones from `docker system df` and `docker ps -a`:

> `docker system prune -a --volumes` would delete 14 stopped containers, 3 networks, 27
> images (about 9 GB, including `postgres:17` and `apache/airflow:2.10.5` which you may
> have to pull again), and 2 anonymous volumes. Your named volume `db-data` is not
> affected. Reclaiming only build cache would free about 5 GB: `docker builder prune`.
> Which do you want?

It lists counts and sizes (from `docker system df` and `docker ps -a`), names anything
likely to matter, says what survives, and offers the narrower command. The user can say
yes in one word, and the answer is informed.

## Related

- `DOCKER-COMPOSE-PATTERNS` for `down -v` and volumes managed by a Compose project.
- `DOCKER-BUILD-STRATEGIES` and `DOCKER-PROJECT-FOUNDATIONS` for the non-destructive work
  that usually comes first.
