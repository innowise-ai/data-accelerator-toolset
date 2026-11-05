#!/usr/bin/env node
// Builds dist/page.html from ../index.json, groups.json and template.html.
// No dependencies. Run: node build.js [--out <file>]
'use strict';
const fs = require('fs');
const path = require('path');
const zlib = require('zlib');
const { execFileSync } = require('child_process');

const here = __dirname;
const outArg = process.argv.indexOf('--out');
const out = outArg > 0 ? path.resolve(process.argv[outArg + 1]) : path.join(here, 'dist', 'page.html');
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
  // One placement is ["group", "subgroup"]; a skill shown in several groups has a list of them.
  const gs = Array.isArray(g[0]) ? g : [g];
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
    gs,
    t: a.topics || [],
    ap: a.applies_to || {},
    n: p.name || a.id,
    sum: p.summary || '',
    b: p.benefits || [],
    rq: a.requires || null,
    nw: previousIds ? !previousIds.has(a.id) : false,
  };
});

// Every file of every artifact, for the page's "Download ZIP". Each file is
// deflated here, so the page only stitches finished entries into a ZIP and
// the embedded payload is about a third of the raw files. The whole directory
// goes in, as the installer copies it.
const crcTable = new Uint32Array(256).map((_, n) => {
  let c = n;
  for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  return c >>> 0;
});
const crc32 = buf => {
  let c = 0xffffffff;
  for (const b of buf) c = crcTable[(c ^ b) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
};
const walk = dir => fs.readdirSync(dir, { withFileTypes: true })
  .sort((a, b) => (a.name < b.name ? -1 : a.name > b.name ? 1 : 0))
  .flatMap(e => (e.isDirectory() ? walk(path.join(dir, e.name)) : [path.join(dir, e.name)]));
const files = {};
let payload = 0;
for (const a of index.artifacts) {
  const root = path.join(here, '..', a.source_path);
  files[a.id] = walk(root).map(f => {
    // The repository stores text with LF (.gitattributes), but a Windows checkout
    // may hold CRLF; a shell script with CRLF fails on Linux. A file with a NUL
    // byte is binary and goes in untouched.
    let bytes = fs.readFileSync(f);
    if (!bytes.includes(0)) bytes = Buffer.from(bytes.toString('latin1').replace(/\r\n/g, '\n'), 'latin1');
    const packed = zlib.deflateRawSync(bytes, { level: 9 }).toString('base64');
    payload += packed.length;
    // A script with a shebang keeps its executable bit after unzip on macOS and Linux.
    const mode = bytes.subarray(0, 2).toString() === '#!' ? 0o755 : 0o644;
    return [path.relative(root, f).split(path.sep).join('/'), crc32(bytes), bytes.length, mode, packed];
  });
}

// The count shown in the intro text follows the index.
let html = template
  .replace('__DATA__', () => JSON.stringify(data).replace(/</g, '\\u003c'))
  .replace('__FILES__', () => JSON.stringify(files))
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

fs.mkdirSync(path.dirname(out), { recursive: true });
fs.writeFileSync(out, html);

console.log(`Built ${path.relative(process.cwd(), out)}: ${data.length} skills from ${index.toolset_ref}`);
console.log(`Embedded skill files for Download ZIP: ${(payload / 1048576).toFixed(2)} MB`);
if (previousIds) {
  const added = data.filter(a => a.nw).map(a => a.id);
  console.log(`New since ${previousTag}: ${added.length ? added.join(', ') : 'none'}`);
}
for (const w of warnings) console.warn('WARNING: ' + w);
