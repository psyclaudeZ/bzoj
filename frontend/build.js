import {build} from 'esbuild';
import {readFile, writeFile} from 'node:fs/promises';

const result = await build({
  entryPoints: ['frontend/editor.js'],
  bundle: true,
  minify: true,
  format: 'iife',
  outfile: 'bzoj/static/editor.bundle.js',
  metafile: true,
  legalComments: 'external',
  banner: {js: '/* Third-party licenses: editor.bundle.LICENSE.txt */'},
});

// Include the licenses of every bundled dependency, grouping identical notices.
const packages = new Set(Object.keys(result.metafile.inputs)
  .map(path => path.match(/^node_modules\/((?:@[^/]+\/)?[^/]+)\//)?.[1])
  .filter(Boolean));
const notices = new Map();
for (const name of [...packages].sort()) {
  const license = (await readFile(`node_modules/${name}/LICENSE`, 'utf8')).trim();
  notices.set(license, [...(notices.get(license) ?? []), name]);
}
await writeFile('bzoj/static/editor.bundle.LICENSE.txt', [...notices]
  .map(([license, names]) => `${names.join(', ')}\n\n${license}\n`).join('\n'));
