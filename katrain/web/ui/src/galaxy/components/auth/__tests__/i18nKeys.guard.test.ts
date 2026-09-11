/* 本轨道所有新增文案键的两道闸，集中在这一个文件。
 *
 * **为什么不跟着各自的组件测试走**：Task 14 建了第一条（30 键 / 2 文件），Task 15 把它扩成
 * 32 键 / 3 文件并另加了「键必须真的落进 11 本 .po」那条；Task 16 的计划原稿又要照抄
 * 一份 10 键 / 4 文件的。两份同形的闸分居两处，**改一处不会有人告诉你另一处坏了** ——
 * 键清单一旦有两份，加键的人只会记得改自己那份。
 * 所以在 Task 16 落地时抽到这里：一张清单、两条闸、一个落点。后续 Task 加键只动这个文件。
 * 命名照仓里现成的 src/api/__tests__/tutorialReadonly.guard.test.ts。
 *
 * 闸扫的是**源码文本**，不去注释里绕 —— 所以 SOURCES 里那几个文件的注释中
 * 不要写形如 `i18n.t('auth:xxx', '...')` 的示例，那会被闸读成真的调用点。 */
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { describe, it, expect } from 'vitest';

/* ⚠️ 不能写 `new URL('../LoginModal.tsx', import.meta.url)`：Vite 会把**字面量**形式的
   `new URL(..., import.meta.url)` 当成资源引用，在 transform 期改写成
   `http://localhost:3000/src/...`，readFileSync 当场 `The URL must be of scheme file`。
   仓里 `src/components/liveBoardWiring.test.ts:13` 那个写法能活，是因为它传的是**变量**，
   Vite 的静态分析只认字面量。走 `src/api/__tests__/tutorialReadonly.guard.test.ts:11` 那条路。
   本轨道在这一个坑上已经栽过三次（T14 实际踩到，T15/T16 的计划原稿各写了一遍）。 */
const HERE = dirname(fileURLToPath(import.meta.url));

/** 闸的操作数在哪它就住哪：这八个文件是本轨道写下新文案键的全部落点。 */
const SOURCES = [
  '../LoginModal.tsx',
  '../CountryCodeSelect.tsx',
  '../PhoneConsent.tsx',
  '../BindPhoneDialog.tsx',
  '../../billing/FreeQuotaNotice.tsx',
  '../../layout/GalaxySidebar.tsx',
  '../../../hooks/live/useComments.ts',
  '../../../../features/report/useReportTasks.ts',
];

const NEW_KEYS = [
  // 界面文案（14）
  'auth:switch_to_phone', 'auth:switch_to_password', 'auth:forgot_password',
  'auth:phone', 'auth:country_code', 'auth:sms_code', 'auth:get_code',
  'auth:resend_after', 'auth:code_submitted', 'auth:err_phone_required',
  'auth:err_code_required', 'auth:err_phone_not_bound', 'auth:err_cooldown',
  'auth:seconds',
  // `describeError` 的 BY_CODE 表（16）—— 计划的键清单漏了这一批，但它们同样是
  // 本 Task 造出来的用户可见文案，同样要中文默认值、同样要进 11 本 .po。
  'auth:err_code_mismatch', 'auth:err_code_expired', 'auth:err_code_used',
  'auth:err_code_locked', 'auth:err_code_not_found', 'auth:err_code_purpose',
  'auth:err_bad_phone', 'auth:err_bad_purpose', 'auth:err_quota_phone',
  'auth:err_capacity', 'auth:err_provider', 'auth:err_phone_taken',
  'auth:err_already_bound', 'auth:err_phone_unbound', 'auth:err_on_device',
  'auth:err_need_online',
  // Task 15 的告知与同意（2）
  'auth:phone_consent', 'auth:privacy_policy',
  /* Task 16 的绑定入口 / 免费额度文案 / 评论被拒回执（9）。
     注意**不是 10 个** —— 计划把 `auth:err_phone_taken` 也列成新键，但它 Task 14 就已经在
     LoginModal 的 BY_CODE 表里了（上面那一批）。BindPhoneDialog 复用那一份默认值，
     不给同一个键写第二份文案：msgstr 在生产里只有一份，两份默认值只会在「字典为空」
     那个退化态里打架，而那正是没人会去看的状态。 */
  'auth:bind_phone', 'auth:bind_btn', 'auth:phone_bound_already',
  'report:free_quota_phone_required', 'report:free_quota_remaining_prefix',
  'report:free_quota_remaining_suffix', 'report:free_quota_used_up',
  'report:free_quota_unavailable', 'live:comment_requires_phone',
  // Task 17 的改密码入口与 402 分支（9）
  'auth:set_password', 'auth:set_password_btn', 'auth:new_password',
  'auth:err_new_password_required', 'auth:set_password_other_devices',
  'auth:set_password_needs_phone', 'auth:err_challenge_phone_mismatch',
  'report:err_402_phone', 'report:err_402_credits',
];

describe('本轨道新增文案键', () => {
  it('每个键都有中文默认值', () => {
    /* 正判，不是反判：反判（「扫出所有英文默认值」）必须维护一份旧键豁免名单，
       而同一个 Task 又要求把触碰到的旧键改成中文，两条指令互相打架（review #39/#55）。
       这里只管本轮显式列出的这批键，旧键完全不在射程内。

       两种引号 + 模板串都认。这不是多此一举：同一个文件里 `auth:switch_to_register` 的
       默认值就是双引号包的（"Don't have an account? Register"，因为文案里有撇号），
       只吃单引号的闸对这条现成的反例是瞎的 —— Step 5 第二条变异钉的就是它。
       `\bt\(` 同时命中 `i18n.t(` 与解构出来的 `t(`。

       它扫的是**源码文本**，不去注释里绕 —— 所以这两个文件里不要写形如
       `i18n.t('auth:xxx', '...')` 的注释，那会让闸读到注释里的那一条。 */
    /* ⚠️ 不能写 `new URL('../LoginModal.tsx', import.meta.url)`：Vite 会把
       **字面量**形式的 `new URL(..., import.meta.url)` 当成资源引用，在 transform 期
       改写成 `http://localhost:3000/src/...`，readFileSync 当场 `The URL must be of scheme file`。
       仓里 `src/components/liveBoardWiring.test.ts:13` 那个写法能活，是因为它传的是**变量**，
       Vite 的静态分析只认字面量。这里走 `src/api/__tests__/tutorialReadonly.guard.test.ts:11` 那条路。 */
    const src = SOURCES.map((rel) => readFileSync(resolve(HERE, rel), 'utf8')).join('\n');

    const missing: string[] = [];
    const notChinese: string[] = [];
    for (const key of NEW_KEYS) {
      const m = src.match(new RegExp(`\\bt\\(\\s*(['"\`])${key}\\1\\s*,\\s*(['"\`])([\\s\\S]*?)\\2`));
      if (!m) { missing.push(key); continue; }
      if (!/[一-龥]/.test(m[3])) notChinese.push(`${key} => ${m[3]}`);
    }
    expect({ missing, notChinese }).toEqual({ missing: [], notChinese: [] });
  });

  it('每个键都真的落进了 11 本 .po', () => {
    /* 上面那条闸只读**源码**，只证「默认值是中文」。它对「键根本没进字典」是绿的 ——
       而那正是 Task 14/15 最容易漏的一步（batch 脚本是写死字典，不改字典跑它，
       `git diff | grep '^+msgid'` 输出是空的，空差异很容易被读成「没有污染」）。
       后果与 Task 14 花一整个步骤解决掉的问题同款：10 种语言在登录框看到整段中文。
       这一条量的是**落地**，不是意图。 */
    const LOCALES = ['en', 'cn', 'tw', 'jp', 'ko', 'de', 'es', 'fr', 'ru', 'tr', 'ua'];
    // __tests__ → auth → components → galaxy → src → ui → web → katrain
    const I18N_ROOT = resolve(HERE, '../../../../../../../i18n/locales');
    // 路径写错时要当场响，不能因为「一个都没找到」而静默变成另一种红。
    expect(existsSync(I18N_ROOT), `i18n 目录没找到：${I18N_ROOT}`).toBe(true);

    const missing: string[] = [];
    for (const lang of LOCALES) {
      const po = readFileSync(resolve(I18N_ROOT, lang, 'LC_MESSAGES/katrain.po'), 'utf8');
      for (const key of NEW_KEYS) {
        if (!po.includes(`msgid "${key}"\n`)) missing.push(`${lang}/${key}`);
      }
    }
    expect(missing).toEqual([]);
  });
});
