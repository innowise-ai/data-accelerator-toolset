#!/usr/bin/env node
// Builds dist/page.html from ../index.json, groups.json and template.html.
// No dependencies. Run: node build.js
'use strict';
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const here = __dirname;
const index = JSON.parse(fs.readFileSync(path.join(here, '..', 'index.json'), 'utf8'));
const groups = JSON.parse(fs.readFileSync(path.join(here, 'groups.json'), 'utf8'));
const ru = JSON.parse(fs.readFileSync(path.join(here, 'ru.json'), 'utf8'));
const template = fs.readFileSync(path.join(here, 'template.html'), 'utf8');

const known = new Set(index.artifacts.map(a => a.id));
const warnings = [];
const version = String(index.toolset_ref || 'unknown').replace(/^refs\/(tags|heads)\//, '');

// "New" means added since the previous release tag. Only additions count:
// most version bumps are small edits, and flagging them would be noise.
const semver = v => (/^v(\d+)\.(\d+)\.(\d+)$/.exec(v) || []).slice(1).map(Number);
const older = (a, b) => { for (let i = 0; i < 3; i++) if (a[i] !== b[i]) return a[i] < b[i]; return false; };
let previousTag = null;
let previousIds = null;
try {
  const git = args => execFileSync('git', args, { cwd: path.join(here, '..'), encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] });
  const current = semver(version);
  if (current.length !== 3) throw new Error(`toolset_ref ${version} is not a vX.Y.Z tag`);
  previousTag = git(['tag', '--list', 'v*', '--sort=-v:refname']).split(/\r?\n/)
    .find(t => semver(t).length === 3 && older(semver(t), current)) || null;
  if (!previousTag) throw new Error(`no release tag older than ${version}`);
  previousIds = new Set(JSON.parse(git(['show', `${previousTag}:index.json`])).artifacts.map(a => a.id));
} catch (e) {
  warnings.push(`cannot read the previous release's index.json (${e.message}); no skill is marked new`);
}

for (const id of Object.keys(ru)) {
  if (!known.has(id)) warnings.push(`ru.json lists ${id}, which is not in index.json`);
}
for (const id of Object.keys(groups)) {
  if (!known.has(id)) warnings.push(`groups.json lists ${id}, which is not in index.json`);
}

const data = index.artifacts.map(a => {
  let g = groups[a.id];
  if (!g) {
    warnings.push(`${a.id} has no entry in groups.json; shown under "General / Other"`);
    g = ['General', 'Other'];
  }
  const p = a.presentation || {};
  const r = ru[a.id];
  if (!r) warnings.push(`${a.id} has no Russian text in ru.json; the RU view shows English for it`);
  else if (r.v !== a.version) warnings.push(`${a.id} is ${a.version} in index.json but its Russian text was written for ${r.v}; re-check ru.json`);
  if (r && a.requires && !r.req) warnings.push(`${a.id} declares requires but ru.json has no req for it; the RU view shows English requirements`);
  if (r && r.req && !a.requires) warnings.push(`${a.id} has req in ru.json but declares no requires in index.json`);
  return {
    ru: r ? { n: r.n, sum: r.sum, b: r.b, rq: r.req || null } : null,
    id: a.id,
    v: a.version,
    p: a.source_path,
    g: g[0],
    s: g[1],
    t: a.topics || [],
    ap: a.applies_to || {},
    n: p.name || a.id,
    sum: p.summary || '',
    b: p.benefits || [],
    rq: a.requires || null,
    nw: previousIds ? !previousIds.has(a.id) : false,
  };
});

// The count shown in the intro text follows the index.
let html = template
  .replace('__DATA__', () => JSON.stringify(data).replace(/</g, '\\u003c'))
  .replace(/__VERSION__/g, version);
html = html.replace(/38 skills/g, `${data.length} skills`).replace(/38 скиллов/g, `${data.length} скиллов`);

// template.html is written as an artifact fragment; wrap it as a full document for Apps Script.
const split = html.indexOf('</style>') + '</style>'.length;
html =
  '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">\n' +
  html.slice(0, split) +
  '\n</head><body>' +
  html.slice(split) +
  '\n</body></html>\n';

fs.mkdirSync(path.join(here, 'dist'), { recursive: true });
fs.writeFileSync(path.join(here, 'dist', 'page.html'), html);

console.log(`Built dist/page.html: ${data.length} skills from ${index.toolset_ref}`);
if (previousIds) {
  const added = data.filter(a => a.nw).map(a => a.id);
  console.log(`New since ${previousTag}: ${added.length ? added.join(', ') : 'none'}`);
}
for (const w of warnings) console.warn('WARNING: ' + w);
