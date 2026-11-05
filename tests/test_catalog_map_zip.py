"""The catalog map's Download ZIP, built by the page's own JavaScript in Node.

Builds the page with catalog-map/build.js, runs the block between ZIP:BEGIN
and ZIP:END on every artifact, and checks the result with zipfile: valid CRCs,
one folder per artifact with exactly the files on disk, executable bits on
scripts, and a README. Needs Node.js; skipped without it.
"""

import json
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "catalog-map" / "build.js"

NODE = r"""
const fs = require('fs');
const [page, out, lang] = process.argv.slice(1);
const html = fs.readFileSync(page, 'utf8');
const line = name => {
  const start = html.indexOf(`const ${name} = `) + `const ${name} = `.length;
  return html.slice(start, start + html.slice(start).search(/;\r?\n/));
};
const code = html.slice(html.indexOf('// ZIP:BEGIN'), html.indexOf('// ZIP:END'));
const DATA = JSON.parse(line('DATA'));
const { bundle, zipBlob } = new Function('DATA', 'FILES', 'REF', code + '; return { bundle, zipBlob };')(
  DATA, JSON.parse(line('FILES')), JSON.parse(line('REF').replace(/'/g, '"')));
const now = new Date(2026, 9, 30, 12, 0, 0);
zipBlob(bundle(DATA.map(a => a.id), lang, now), now).arrayBuffer()
  .then(b => fs.writeFileSync(out, Buffer.from(b)));
"""


@unittest.skipUnless(shutil.which("node"), "needs Node.js")
class CatalogMapZipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = json.loads((ROOT / "index.json").read_text(encoding="utf-8"))
        cls.tmp = tempfile.TemporaryDirectory(prefix="catalog-map-zip-test-")
        page = Path(cls.tmp.name) / "page.html"
        subprocess.run(["node", str(BUILD), "--out", str(page)], check=True,
                       capture_output=True, text=True)
        cls.zips = {}
        for lang in ("en", "ru"):
            out = Path(cls.tmp.name) / f"skills-{lang}.zip"
            subprocess.run(["node", "-e", NODE, str(page), str(out), lang], check=True,
                           capture_output=True, text=True)
            cls.zips[lang] = zipfile.ZipFile(out)

    @classmethod
    def tearDownClass(cls):
        for z in cls.zips.values():
            z.close()
        cls.tmp.cleanup()

    def test_crcs_are_valid(self):
        for lang, z in self.zips.items():
            with self.subTest(lang=lang):
                self.assertIsNone(z.testzip())

    def test_each_artifact_is_a_folder_with_the_files_on_disk(self):
        z = self.zips["en"]
        expected = {"README.txt"}
        for artifact in self.index["artifacts"]:
            source = ROOT / artifact["source_path"]
            for f in source.rglob("*"):
                if f.is_file():
                    name = f"{artifact['id']}/{f.relative_to(source).as_posix()}"
                    expected.add(name)
                    # Text goes in with LF, as the repository stores it, whatever the checkout has.
                    data = f.read_bytes()
                    if b"\0" not in data:
                        data = data.replace(b"\r\n", b"\n")
                    self.assertEqual(z.read(name), data, name)
        self.assertEqual(set(z.namelist()), expected)

    def test_scripts_keep_the_executable_bit(self):
        z = self.zips["en"]
        for info in z.infolist():
            mode = stat.S_IMODE(info.external_attr >> 16)
            is_script = z.read(info.filename)[:2] == b"#!"
            self.assertEqual(mode, 0o755 if is_script else 0o644, info.filename)

    def test_readme_names_the_version_the_agents_and_every_skill(self):
        version = self.index["toolset_ref"].rsplit("/", 1)[-1]
        for lang, z in self.zips.items():
            with self.subTest(lang=lang):
                text = z.read("README.txt").decode("utf-8")
                self.assertIn(version, text)
                for folder in (".claude/skills/", ".agents/skills/", ".cursor/skills/"):
                    self.assertIn(folder, text)
                for artifact in self.index["artifacts"]:
                    self.assertIn(f"  {artifact['id']}  {artifact['version']}", text)


if __name__ == "__main__":
    unittest.main()
