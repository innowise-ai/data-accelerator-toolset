---
name: request-refinement
description: Rewrites a rough request into a complete one before any work starts - reads only what the request needs from the project, searches the web only for facts the project cannot hold, asks only about what neither can answer, shows the rewritten request and waits for confirmation, then works from it. Run it by typing /request-refinement followed by the request; it never starts by itself.
disable-model-invocation: true
---

# Refining a request before work starts

A request typed in a hurry carries the part its author thought to write. The rest,
such as which model, which environment, what must not change and how to tell it
worked, the author knows and leaves out, and the agent fills those gaps with
plausible guesses. Each guess is invisible in the result. The work looks finished
and is judged wrong at review, long after the cheapest moment to correct the guess.

This command moves the guessing to the front. Before any work, the agent reads the
request, fills what the project already answers, checks outside facts the request
depends on, asks about what is left, and shows the request as it now understands
it. The user corrects a paragraph instead of a pull request.

It runs only when the user calls it, which means the user has already decided this
request is worth a minute of setup. That is why nothing here decides *whether* to
refine: being called is the decision. It is also why the rewrite is shown and
confirmed rather than applied silently.

Three decisions shape the run: whether to ask before looking, what to read, and
whether to search the web. Each has a default and a short list of exceptions,
because agents left to judge effort on their own tend to over-read on small
requests and under-read on large ones.

## What this is not

**Not requirements discovery.**
[Requirements brainstorming](../REQUIREMENTS-BRAINSTORMING/SKILL.md) works out what
should be built when the goal itself is open: the real need, the alternatives, the
non-goals of a design. This command takes one request whose goal is known and makes
it precise enough to execute. If filling the gaps shows that the goal is not known,
because the request could reasonably mean two different pieces of work, or the open
questions are about *what* to build rather than *where* and *how*, say so and
suggest working that out first. A neat rewrite that hides an open decision is worse
than no rewrite.

**Not prompt writing.** It does not write prompts for subagents or for LLM steps in
a pipeline, and it does not produce a reusable prompt or skill. Its output is the
task the agent itself is about to do.

## First: ask now, or look first

**Look first.** A question asked before reading the project is usually one a file
could have answered, or one whose options the agent cannot yet name, so the user
gets more questions and vaguer ones. A question asked after a short look offers the
real alternatives and is answered at a glance. Agents that explore first ask fewer
questions and better ones.

Ask before looking only when looking cannot help:

- **There is no request.** The user typed the command alone. Ask for the request and
  stop.
- **The request points at material the agent cannot reach**, such as a ticket link
  with no connector, "the numbers from yesterday's call" or an attachment that is
  not there. Ask for the text. Do not reconstruct a ticket from its title.
- **The request is not about anything in reach.** There is no repository, or the
  request concerns a system the agent cannot see. Then the project has nothing to
  add, and the questions are the whole refinement.
- **One answer decides where to look at all**, for example a workspace with several
  unrelated projects and a request that names none. Ask that one question, then
  continue as normal.

Even then, ask only the blocking question now. The rest waits until after looking,
in the single round described below.

## What a complete request contains

A request is ready when the agent could start without inventing anything that
matters. In practice that means answers for these slots:

| Slot | What it pins down | A typical gap in data work |
|---|---|---|
| Outcome | What is true afterwards | "Fix the orders model": fix which symptom? |
| Target | Files, models, tables, DAGs, environment | `orders` exists in staging and in marts |
| Inputs | Sources, period, volume | Which date range a backfill covers |
| Constraints | What must not change, conventions to follow | Column names a dashboard reads |
| Done when | A check someone can observe | `dbt build -s fct_orders+` passes and the row count is unchanged |
| Out of scope | Where to stop | Tidying neighbouring models along the way |
| Deliverable | What is handed over | A diff, a pull request, a query, a short note |

Most requests need only some of them. Renaming one function in one file needs a
target and nothing else, and forcing every slot into it produces a rewrite longer
than the work, which is friction the user called the command to avoid.

## Read what the request needs from the project

Most gaps can be closed without the user. Look in this order, which is also the
order of trust when two sources disagree:

1. **This conversation.** What the user already said outranks anything inferred.
2. **The project's instructions for agents:** `CLAUDE.md`, `AGENTS.md`, rules files,
   and the `Project context` sections that project adaptation adds to installed
   skills. These are written for exactly this purpose and are cheap to read, so read
   them first and in full.
3. **The Accelerator profile**, `.accelerator/profile.json`, when it exists: the
   languages and frameworks detected and what the team chose to work on.
4. **The repository:** the code and configuration the request names or implies,
   such as `dbt_project.yml`, schema files, the DAG folder and the tests; the naming
   used by neighbouring files; the current branch and recent commits.
5. **The installed skills that will do the work.** Their checks or output format
   often define what "done" means here.

**Follow pointers, do not survey.** Start from the nouns in the request: search for
them, list the directories they lead to, and open only the files that fill a slot.
File names, sizes and folder layout already say a lot before anything is opened.
Make independent reads in parallel. Reading the whole repository "for context" fills
the agent's context with material the rewrite does not use and slows everything
after it.

**Scale the reading to the request.** A change to one named file needs a handful of
reads. A change that crosses models or services needs more, still aimed at the
slots. When the reading keeps branching without filling slots, that is
investigation, which belongs to the work itself: stop, and turn what is unresolved
into a question or a stated assumption.

**Only what was opened counts.** A value enters the rewrite as "from the project"
only if the agent read the file that holds it, and the rewrite names that file. A
plausible guess about code nobody opened is exactly the guess this command exists to
catch, presented as a fact.

**Read, do not run.** Reading files, listing directories and searching are part of
this step. Running builds or tests, querying a warehouse and changing anything are
not: that is the work, and doing it before the user has seen the rewrite defeats the
point. Configuration that holds credentials, such as `profiles.yml` or `.env`, is
read for its structure (which targets exist) and never quoted into the rewrite.

## Search the web only for what the project cannot know

Most requests need no web search: their gaps are about this project and this user,
and no page on the internet knows which `orders` model was meant. A search is worth
running when all of these hold:

- the request depends on an **outside fact**: how a tool, library, service or API
  behaves, a limit or quota, a deprecation, what changed between versions;
- the fact **can change**, so what the agent remembers may be out of date;
- the project **does not settle it**: no pinned behaviour, vendored docs or
  instructions that already answer it;
- the answer **would change the rewrite**: a different target version, an extra
  constraint, a step that is no longer possible.

The project still comes first, because it says *which* version or service the
question is about: `packages.yml`, a lock file or a provider pin decides which docs
are relevant. Use links the user gave before searching. Then go to primary sources,
meaning the vendor's documentation, release notes and changelog for that version,
rather than blog posts and aggregator pages, which are often older than they look.

Keep it short: a couple of searches, stopping as soon as the fact is confirmed. List
each fact the search contributed under its own heading in the rewrite, with the
link, so the user can see what came from outside. When a finding changes what the
user asked for, such as a deprecated option or a breaking change in the target
version, raise it as a question rather than quietly adapting the request. When no
web access is available, write the fact as an unverified assumption.

## Ask only what changes the work

What is left falls into three kinds:

- **A gap whose possible answers lead to materially different work, and which
  neither the project nor a search can answer, becomes a question.** These are
  usually about intent, priorities and business rules: what the user wants, not
  where something is.
- **A gap where some choice has to be made to do the work gets a sensible default,**
  written into the rewrite as an assumption the user can overturn.
- **A gap that nothing depends on stays open.** Write "no constraint" or leave the
  slot out. Inventing a value for it only adds a detail the user has to check.

Asking costs something both ways. Too few questions and the agent fills gaps with
invented values; too many and the user does the work the command was meant to save.
Ask in one round, usually no more than three questions. Each question names the
concrete options found while looking, marks the default, and fits on one line, so
it can be answered at a glance: "`orders` is a staging model (`stg_orders`) and a
mart (`fct_orders`); which one? (default: `fct_orders`)" rather than "which orders
model?". Do not ask where something is when one more search would find it, and do
not ask what the user already said.

If nothing was added and nothing needs asking, say so in one line and show the
request unchanged. The user called the command and gets an answer, but padding an
already clear request is noise.

## Show the rewrite and wait

Write the refined request as text the user could have typed: plain instructions, in
the user's language, no longer than the task needs. Under it, list what was added
and where it came from, then the questions. Then stop.

Do not start the work while waiting, not even the parts that look certain. The
confirmation exists so that nothing is done on an understanding the user has not
seen.

```markdown
**Refined request**

> <the request as a complete instruction: outcome, target, constraints, done when, out of scope>

**Added**
- From the project: <what> - <value> (<file, or "you said earlier">)
- From the web: <fact> - <link>
- Assumed: <what> - <default>; say if this is wrong

**Questions**
1. <question>: <option A> (default) / <option B>

Reply with answers or edits, or "go" to start from this version.
```

Treat each answer as a constraint on the request rather than text to append: apply
it, then check whether it settles other gaps or opens a new one. A question left
unanswered takes its stated default; do not ask it again. If an answer changes the
work materially, such as a different target or a wider scope, show the updated
version once more. Otherwise confirm it in one line and start. A second round of
questions is justified only when an answer opened a gap that changes the work; more
rounds than that mean the goal was not known, which is the requirements
brainstorming case above.

## Work from the refined request

Once confirmed, the refined request is the task. Check the result against its "done
when" before reporting, and stop at its "out of scope".

The original request keeps authority over intent. The rewrite adds precision, not
purpose. If the refined text and the original disagree about what the user wanted,
the original wins and the rewrite was wrong. The same test catches scope creep while
writing it: every added line should read to the user as "yes, that is what I meant",
never as a new idea.

## Examples

### Filled from the project, no search

The user types `/request-refinement add a test that orders have no duplicates`.

Searching for `orders` finds `models/staging/stg_orders.sql` and
`models/marts/fct_orders.sql`. The mart is one row per order line, keyed by
`order_id` and `line_number`; its tests live in `models/marts/_marts.yml`; and
`dbt_utils` is already in `packages.yml`. Nothing here depends on an outside fact,
so there is no search.

```markdown
**Refined request**

> Add a uniqueness test to `fct_orders` on the combination of `order_id` and
> `line_number`, using `dbt_utils.unique_combination_of_columns` in
> `models/marts/_marts.yml`. Run `dbt test -s fct_orders` and report the result. If
> the test fails on current data, list the duplicate keys; do not change the model.

**Added**
- From the project: the grain is one row per order line (`fct_orders.sql`), so a
  plain `unique` test on `order_id` would fail on valid data
- From the project: mart tests live in `models/marts/_marts.yml`, and `dbt_utils` is
  already a dependency
- Assumed: duplicates found by the test are reported, not fixed; say if they should
  be fixed too

**Questions**
1. Should `stg_orders` get the same test?: only `fct_orders` (default) / both

Reply with answers or edits, or "go" to start from this version.
```

Taken literally, the original request most likely ends as a `unique` test on
`order_id`, added to whichever model was found first, which fails on valid data the
first time it runs.

### An outside fact decides the rewrite

The user types `/request-refinement upgrade dbt to the latest version`.

The project pins `dbt-core` and the warehouse adapter in `requirements.txt`, and
`packages.yml` pins `dbt_utils`. What "latest" is, and what breaks on the way to it,
is not in the project and changes with every release, so this is where a search
belongs: the dbt release notes and upgrade guides for each minor version between
the pinned one and the current one, plus the compatibility notes for the adapter and
for `dbt_utils`. The rewrite names the target version, lists the breaking changes
that touch this project's code with links, and asks one question if a breaking change
needs a decision, such as whether to migrate a deprecated config now or pin below the
version that removes it.
