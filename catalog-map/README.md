# catalog-map

A single-page map of the catalog (groups, topics, what each skill applies to), shared as a Google Apps Script web app. English by default, with an EN/RU switch.

```
../index.json + groups.json + template.html  --node build.js-->  dist/page.html  --clasp-->  /exec link
```

## Update after a catalog release

```bash
node build.js && clasp push -f && clasp update-deployment AKfycbx3VvBBbugxxs35navMHVDBCyPgca4eSgbmNljWOwpR-OYo-b7NpUsWKj_MB5nrPHp5Uw
```

Use `update-deployment`, not `create-deployment`: the second one creates another link, and the old link keeps serving the old page. `push` alone publishes nothing, because `/exec` serves the last deployed version.

Russian names, summaries and benefits live in `ru.json`, keyed by artifact id, with the artifact version they were written for. `build.js` warns when an artifact has no Russian text or when its version moved since the text was written; until then the RU view shows English for it.

An artifact's `requires` from `index.json` shows on its card under "What it needs"; its Russian text is `req` in the same `ru.json` entry, with the same `tools`/`access` keys. `build.js` warns when one side has it and the other does not.

A skill whose id is not in the previous release's `index.json` gets a "new" tag. `build.js` finds that release as the highest `vX.Y.Z` tag older than `toolset_ref` and reads its index with `git show`, so it needs a clone with tags. If that fails it warns and builds with no "new" tags. Skills whose version moved are not marked: most bumps are small edits, and marking them would be noise. The build prints which ids it marked. A "new (N)" chip in the topic row filters to them, and is hidden when the release added nothing.

`build.js` warns when an artifact in `index.json` has no entry in `groups.json`. Add the id to `groups.json` as `["<group>", "<subgroup>"]`. Groups are `Data engineering`, `Containers`, `Infrastructure as code` and `General`; a new subgroup name shows in English in both languages unless you add it to `SUB_RU` in `template.html`.

## Link

<https://script.google.com/a/macros/innowise.com/s/AKfycbx3VvBBbugxxs35navMHVDBCyPgca4eSgbmNljWOwpR-OYo-b7NpUsWKj_MB5nrPHp5Uw/exec>

Access is limited to the `innowise.com` domain (`appsscript.json`, `"access": "DOMAIN"`).

- deploymentId: `AKfycbx3VvBBbugxxs35navMHVDBCyPgca4eSgbmNljWOwpR-OYo-b7NpUsWKj_MB5nrPHp5Uw`
- scriptId: `1nOHIq-G65y_TxsKkgrIraiWuMzjRPkEJ7cm1fTjUBWJQVfNa-LJHj25e`

## Creating the project again

`clasp create-script` overwrites `dist/appsscript.json` and drops the `webapp` block, which makes the page return 404. Restore the manifest from git before `clasp push -f`.

Needs clasp 3.x, the Apps Script API switched on for the working account, and `clasp login` under that account.
