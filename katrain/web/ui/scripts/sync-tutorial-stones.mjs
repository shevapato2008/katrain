import { copyFile, mkdir, readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

// Explicit mirror between the existing APP and console UIs; no package or runtime dependency.
const [targetUi, flag] = process.argv.slice(2);
if (!targetUi || (flag && flag !== '--check')) throw new Error('Usage: node scripts/sync-tutorial-stones.mjs TARGET_UI [--check]');
const source = fileURLToPath(new URL('../', import.meta.url));
const manifest = JSON.parse(await readFile(resolve(source, 'src/assets/tutorial-stones/manifest.json'), 'utf8'));
const files = [
  'src/components/tutorials/tutorialStoneSprites.ts',
  'src/components/tutorials/tutorialStoneSprites.test.ts',
  'src/assets/tutorial-stones/manifest.json',
  ...manifest.files.map(({ file }) => `src/assets/tutorial-stones/${file}`),
];
for (const file of files) {
  const from = resolve(source, file), to = resolve(targetUi, file);
  if (flag === '--check') {
    if (!(await readFile(from)).equals(await readFile(to))) throw new Error(`Stone mirror differs: ${file}`);
  } else {
    await mkdir(resolve(to, '..'), { recursive: true });
    await copyFile(from, to);
  }
}
console.log(`${flag === '--check' ? 'Verified' : 'Copied'} ${files.length} identical stone files.`);
