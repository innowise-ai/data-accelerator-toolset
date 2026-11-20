# Who to ask about what

Read this before writing the "Who to ask about what" section of the knowledge base,
on the first run and on every later one, since the section is rebuilt each time.

What a newcomer cannot find by reading is who knows a part of the system. The
repository's history gives a good first answer: the people who changed an area most
in recent months are usually the ones who can explain it. It is a first answer, not
ownership, which is why the section is written as "who to ask about X" and not as
"owner".

Work it out for each module from [How it is built](knowledge-base.md#how-it-is-built), over a
recent window: six months by default, or since the module last changed shape if
that is shorter. A window keeps the people who left two years ago from heading the
list.

```bash
# commits per person in the window, merge commits excluded
git shortlog -sn --no-merges --since='6 months ago' HEAD -- <module path>
# each person's latest change in the window (log is newest first)
git log --no-merges --since='6 months ago' --format='%an|%ad' --date=short -- <module path> \
  | awk -F'|' '!seen[$1]++'
# who started the module, often the one who knows why it is shaped this way
git log --reverse --no-merges --format='%ad %an' --date=short -- <module path> | head -3
```

Then correct for what the counts get wrong, and say in the section which
corrections were made:

- **Merges and squashes.** `--no-merges` drops merge commits, whose author is
  whoever merged. Count authors (`%an`), not committers: with squash or rebase
  merging the committer is the code host or the person who pressed the button.
  Where the team lands other people's work, `Co-authored-by` trailers name the
  rest.
- **Bots.** Dependency updaters, release and formatting bots and CI accounts commit
  often and can answer nothing. Leave out authors whose names end in `[bot]` or
  that are plainly automation.
- **Mass changes.** One commit that reformats, renames or moves a whole module
  makes its author look like the module's expert. If the repository has
  `.git-blame-ignore-revs`, leave out the commits it lists. Otherwise look at the
  largest commits in the window (`git log --no-merges --since='6 months ago'
  --shortstat --format='%h %an %s' -- <module path>`) and leave out those that only
  reformat, rename or move, naming them.
- **One person, several identities.** People commit under more than one name or
  address. `git shortlog -sne HEAD` shows the addresses so the identities can be
  merged, and `.mailmap` may already merge them. Use the addresses to merge, and
  never copy them into the guide.
- **People who have left.** History cannot tell who is still on the project. Give
  each person's latest change in the window, so a name whose last commit was five
  months ago reads as such, and have the lead confirm the table before it is
  shared (see [Where the guide goes](../SKILL.md#where-the-guide-goes)).
- **A count is not expertise.** Twenty small fixes and one redesign are not
  comparable, and someone who reviews every change to a module may know it best
  with no commits in it. Where the code host is in the plan, add who reviewed the
  merged pull requests that touched the module, for example from
  `gh pr list --state merged --search 'merged:>=<date>' --json number,author,reviews,files`.

`CODEOWNERS` is the team's own declaration and comes first where it exists. When it
and the history disagree, show both: a `CODEOWNERS` file nobody has updated since
the team changed is common, and worth reporting as a gap. A shallow clone has
almost no history to count (`git rev-parse --is-shallow-repository` prints
`true`); say so rather than ranking the few commits it holds.

For each module, name two or three people with what to ask them about, taken from
what their commits changed: "ask about the incremental models in
`models/marts/finance/`", not "finance owner". Write names only. Above the table,
state the window and what was left out, so the reader knows what the order means.
