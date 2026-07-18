import { writeFile } from 'node:fs/promises';

const manifestUrl = new URL('../../static-kiosk-2d/.smartbox-build.json', import.meta.url);
const manifest = JSON.stringify({ box_sso_strict: true, schema: 1 });

await writeFile(manifestUrl, manifest, 'utf8');
