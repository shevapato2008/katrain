import { useTranslation } from '../../../hooks/useTranslation';
import { Icon } from '../../shell/icons';
import { PLATFORM_META } from '../../constants/platforms';
import { LOGIN_FACTS } from '../../constants/platformLoginFacts';

/**
 * 登录页左栏(`.xplogin__aside`,设计源 `go-kiosk.tmpl.html:1391-1417`)。
 *
 * `LOGIN_FACTS[platform]` 是**变量**传给 `t()` 的(`t(f.titleKey, f.titleZh)`),
 * `test_kiosk_i18n.py` 那条通用正则(只认两个单引号字面量)看不见这几条调用 ——
 * 所以它们要在 `test_login_facts_keys_are_translated`(Task 5 Step 6)里单独点名,
 * 靠正则扫源码「找到就该翻」不够,得靠一张表「该有就必须有」。
 *
 * `PLATFORM_LOGIN_ICON` 只覆盖今天真能登录的两家(golaxy/ogs)——野狐 `comingSoon`,
 * 到不了这一屏(`PlatformConnectPage.canLogIn` 和 `PlayPage` 的卡片都先把它挡在外面)。
 */
const PLATFORM_LOGIN_ICON = {
  golaxy: 'globe-hemisphere-west',
  ogs: 'globe-hemisphere-west',
} as const;

export function PlatformLoginAside({ platform }: { platform: string }) {
  const { t } = useTranslation();
  const meta = PLATFORM_META[platform];
  const facts = LOGIN_FACTS[platform] ?? [];
  const name = meta ? t(meta.label, meta.labelCn) : platform;

  return (
    <aside className="xplogin__aside">
      <div className="xpwho">
        <span className="mark" aria-hidden="true">
          <Icon name={PLATFORM_LOGIN_ICON[platform as keyof typeof PLATFORM_LOGIN_ICON] ?? 'globe-hemisphere-west'} />
        </span>
        <div>
          <b>{name}</b>
          {/* 域名/标识是**数据**,不是文案 —— 不走 t(),两家各自的真域名/身份原样显示。 */}
          <span>{platform === 'ogs' ? 'online-go.com' : '19x19.com'}</span>
        </div>
      </div>
      <div className="xpfacts">
        {facts.map((f) => (
          <div key={f.titleKey}>
            <b>{t(f.titleKey, f.titleZh)}</b>
            <p>{t(f.bodyKey, f.bodyZh)}</p>
          </div>
        ))}
      </div>
    </aside>
  );
}

export default PlatformLoginAside;
