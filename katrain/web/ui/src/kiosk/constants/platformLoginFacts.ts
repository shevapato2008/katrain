/**
 * 登录页左栏那几条「登录之前要知道的」。
 *
 * **这里只放 key,中文在 `.po` 里** —— 闸 `test_kiosk_i18n.py` 认的是
 * `t('key','中文')` 这个调用形状,把中文摆在常量表里它看不见,于是这几段
 * 永远不会被翻译,在韩文界面上安静地显示中文。
 */
export interface LoginFact { titleKey: string; titleZh: string; bodyKey: string; bodyZh: string; }

export const LOGIN_FACTS: Record<string, LoginFact[]> = {
  golaxy: [
    { titleKey: 'platform:fact_whose', titleZh: '用谁的账号',
      bodyKey: 'platform:fact_whose_golaxy',
      bodyZh: '星阵自己的账号，不是智星盒的。没有就在手机上的星阵 APP 注册——盒上注册不了。' },
    { titleKey: 'platform:fact_three_ways', titleZh: '三种都能用',
      bodyKey: 'platform:fact_three_ways_body',
      bodyZh: '扫码一个字都不用打；验证码等一条短信；密码最快，但要在触屏上敲。' },
    { titleKey: 'platform:fact_stored', titleZh: '盒上留下什么',
      bodyKey: 'platform:fact_stored_golaxy',
      bodyZh: '只留星阵发的登录令牌，不留密码。想断开随时去设置里。' },
  ],
  ogs: [
    { titleKey: 'platform:fact_whose', titleZh: '用谁的账号',
      bodyKey: 'platform:fact_whose_ogs',
      bodyZh: 'online-go.com 的账号。注册要在浏览器里做，盒上做不了。' },
    { titleKey: 'platform:fact_only_one', titleZh: '盒上只做这一种',
      bodyKey: 'platform:fact_only_one_body',
      bodyZh: 'OGS 网页上还能用 Google、Apple 等账号；那条要跳浏览器，留给出海版。' },
    { titleKey: 'platform:fact_third_party', titleZh: '用第三方注册的',
      bodyKey: 'platform:fact_third_party_body',
      bodyZh: '那种账号没有 OGS 密码，得先去 OGS 网页上设一个。' },
    { titleKey: 'platform:fact_stored', titleZh: '盒上留下什么',
      bodyKey: 'platform:fact_stored_ogs',
      bodyZh: '只留登录后的会话，不留密码。想断开随时去设置里。' },
  ],
};
