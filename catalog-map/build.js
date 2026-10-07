#!/usr/bin/env node
// Builds dist/page.html from ../index.json, groups.json and template.html.
// No dependencies. Run: node build.js
'use strict';
const fs = require('fs');
const path = require('path');

const here = __dirname;
const index = JSON.parse(fs.readFileSync(path.join(here, '..', 'index.json'), 'utf8'));
const groups = JSON.parse(fs.readFileSync(path.join(here, 'groups.json'), 'utf8'));
const template = fs.readFileSync(path.join(here, 'template.html'), 'utf8');

const known = new Set(index.artifacts.map(a => a.id));
const warnings = [];

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
  return {
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
  };
});

// The count shown in the intro text follows the index.
const version = String(index.toolset_ref || 'unknown').replace(/^refs\/(tags|heads)\//, '');
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
for (const w of warnings) console.warn('WARNING: ' + w);
