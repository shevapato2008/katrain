import { useTranslation } from '../../../hooks/useTranslation';
import { Icon } from '../../shell/icons';
import { PLATFORM_META } from '../../constants/platforms';
import { PLATFORM_MARKS } from '../../constants/platformMarks';
import { LOGIN_FACTS } from '../../constants/platformLoginFacts';

/** 查不到品牌标记时才用 —— 见 `constants/platformMarks.ts` 头上那段「查不到就回落,不抛」。 */
const FALLBACK_ICON = 'globe-hemisphere-west' as const;

/**
 * 登录页左栏(`.xplogin__aside`,设计源 `go-kiosk.tmpl.html:1391-1417`)。
 *
 * `LOGIN_FACTS[platform]` 是**变量**传给 `t()` 的(`t(f.titleKey, f.titleZh)`),
 * `test_kiosk_i18n.py` 那条通用正则(只认两个单引号字面量)看不见这几条调用 ——
 * 所以它们要在 `test_login_facts_keys_are_translated`(Task 5 Step 6)里单独点名,
 * 靠正则扫源码「找到就该翻」不够,得靠一张表「该有就必须有」。
 *
 * 标记来自 `constants/platformMarks.ts`(三家都有)。这一屏今天只到得了 golaxy/ogs
 * 两家——野狐 `comingSoon`,`PlatformConnectPage.canLogIn` 和 `PlayPage` 的卡片
 * 都先把它挡在外面了;`FALLBACK_ICON` 那条回落因此在这一屏上今天跑不到,
 * 留着是因为平台列表由服务端下发,多一家是正常事件。
 */
export function PlatformLoginAside({ platform }: { platform: string }) {
  const { t } = useTranslation();
  const meta = PLATFORM_META[platform];
  const facts = LOGIN_FACTS[platform] ?? [];
  const mark = PLATFORM_MARKS[platform];
  const name = meta ? t(meta.label, meta.labelCn) : platform;

  return (
    <aside className="xplogin__aside">
      <div className="xpwho">
        {/* 标记和卡片那边共用同一张表、同一组 CSS(`.is-brand` / `.is-disc`),
            两个槽的几何不同(42 vs 40)但语气一致 —— 都是「放外来物的凹槽」。 */}
        <span className={`mark${mark ? ` is-brand${mark.disc ? ' is-disc' : ''}` : ''}`} aria-hidden="true">
          {mark ? <img src={mark.src} alt="" /> : <Icon name={FALLBACK_ICON} />}
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
