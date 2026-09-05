/** 工信部下发给 modelstella.com 的网站备案号（主办单位：北京万智星科技有限公司）。 */
export const ICP_FILING_NUMBER = '京ICP备2026047949号';

export const MIIT_FILING_URL = 'https://beian.miit.gov.cn/';

/** 备案主体域名。子域一并算数——备案按域名下发，子域跟随主域。 */
const FILED_DOMAIN = 'modelstella.com';

/* 备案号只能挂在**它自己那个域名**上。
 *
 * 测试环境 go.sailorvoyage.top 与开发机 localhost 都不在这张备案下，
 * 在那里印「京ICP备2026047949号」是**假信息**，比不印更糟。所以判据落在浏览器
 * 实际访问的 host 上，而不是构建产物上 —— 同一份 dist 会同时发到测试与生产两台机器。
 *
 * `endsWith('modelstella.com')` 是错的：`evilmodelstella.com` 也会命中。
 * 必须是「等于主域」或「以 `.主域` 结尾」。 */
export const shouldShowIcpFooter = (hostname: string): boolean =>
  hostname === FILED_DOMAIN || hostname.endsWith(`.${FILED_DOMAIN}`);
