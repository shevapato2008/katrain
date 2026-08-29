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

// 共享地界(两个 bundle 都会打进去的那些目录)**谁都不许指回去**。
//
// 上面两条守的是「A 别碰 B」;这一条守的是**中间那一层别碰任何一边** ——
// 它是前两条的前提:共享文件一旦 import 了 kiosk,galaxy 那个 bundle 就跟着把 kiosk
// 拖进来了,而 `no-restricted-imports` 只看**写在源文件里的那一行**,
// 跨一层中转就完全看不见。`npm run verify:kiosk-2d` 也一样 ——
// 它 grep 的是 dist 里的 `three` / `@react-three` 字串,不是这条边界。
//
// ⚠️ `src/features/` **不在 CLAUDE.md 的共享地界清单里,但它就是共享地界**:
// `aiLadder` 和 `report` 两家,kiosk 和 galaxy 各有若干消费者(2026-08-26 实测)。
// 清单该更新,而这条规则不等清单。
const forbiddenFromShared = [
  {
    group: ['**/kiosk/**', '*/kiosk/*', '../kiosk/*', '../../kiosk/*', '../../../kiosk/*'],
    message: 'shared code must not import kiosk — it would drag the kiosk UI into the galaxy bundle',
  },
  {
    group: ['**/galaxy/**', '*/galaxy/*', '../galaxy/*', '../../galaxy/*', '../../../galaxy/*'],
    message: 'shared code must not import galaxy — it would drag the admin UI into the kiosk bundle',
  },
  {
    group: ['**/pages/**', '*/pages/*', '../pages/*', '../../pages/*', '../../../pages/*'],
    message: 'shared code must not import src/pages — those are server-UI routes, not shared territory',
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
  {
    // `src/components/Board3D/**` 不在里面 —— 它是 galaxy 专用件(kiosk 那条规则已禁掉它),
    // 共享地界这条不该管到它头上。
    files: [
      'src/components/**/*.{ts,tsx}',
      'src/hooks/**/*.{ts,tsx}',
      'src/context/**/*.{ts,tsx}',
      'src/features/**/*.{ts,tsx}',
      'src/api/**/*.{ts,tsx}',
      'src/utils/**/*.{ts,tsx}',
      'src/types/**/*.{ts,tsx}',
      'src/api.ts', 'src/theme.ts', 'src/i18n.ts',
    ],
    // 测试文件不在**任何一个 bundle** 里(没有 src 代码 import 它们,Rollup 从入口出发够不着),
    // 而这条规则守的正是「bundle 里会出现什么」。共享件的测试要证明「kiosk 那一侧也读同一把开关」
    // 时,必须能 import 过去 —— 那是判据本身,不是违规。
    ignores: ['src/components/Board3D/**', '**/*.test.{ts,tsx}', '**/__tests__/**'],
    rules: {
      'no-restricted-imports': ['error', { patterns: forbiddenFromShared }],
    },
  },
])
