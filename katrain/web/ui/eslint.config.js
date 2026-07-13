import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

// SBC build boundary — kiosk bundle must not reach galaxy / VideoRecorder / Board3D.
// three.js was REMOVED from the kiosk bundle on 2026-07-13 (3D board dropped to free ~321MB
// of Mali GPU memory contending with KataGo's OpenCL — see
// docs/superpowers/plans/2026-07-13-sbc-3d-off-camera-wb-calib-redesign.md).
// The build-time gate is `npm run verify:kiosk-2d`; these ESLint rules surface violations
// earlier (at edit time) so regressions can't slip into a PR.
const forbiddenFromKiosk = [
  {
    group: ['**/galaxy/**', '*/galaxy/*', '../galaxy/*', '../../galaxy/*', '../../../galaxy/*'],
    message: 'kiosk bundle must not import galaxy code — would drag in admin UI',
  },
  {
    group: ['**/pages/VideoRecorderPage*', '*/pages/VideoRecorderPage', '../pages/VideoRecorderPage'],
    message: 'kiosk bundle must not import VideoRecorderPage — recorder-only',
  },
  {
    group: ['**/components/Board3D/**', '*/components/Board3D/*', '../components/Board3D', '../../components/Board3D', '../../../components/Board3D'],
    message: 'kiosk bundle must not import Board3D — 3D removed from kiosk to free Mali GPU (2026-07-13)',
  },
]

const forbiddenFromServer = [
  {
    group: ['**/kiosk/**', '*/kiosk/*', '../kiosk/*', '../../kiosk/*', '../../../kiosk/*'],
    message: 'galaxy/server UI must not import kiosk code — kiosk is a standalone SBC bundle',
  },
]

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
  },
  {
    files: ['src/kiosk/**/*.{ts,tsx}'],
    rules: {
      'no-restricted-imports': ['error', { patterns: forbiddenFromKiosk }],
    },
  },
  {
    files: ['src/galaxy/**/*.{ts,tsx}', 'src/pages/**/*.{ts,tsx}', 'src/ZenModeApp.tsx'],
    rules: {
      'no-restricted-imports': ['error', { patterns: forbiddenFromServer }],
    },
  },
])
