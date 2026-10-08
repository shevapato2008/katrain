# 四个普通话棋手姓名的来源与有限规则审核

审核人：`/root/zh_ko_native_adapter_review_astra`，`gpt-6-astra / max`，2026-10-09。结论：**通过以下四个精确读音输入及十个新增音节映射；不签署实际数据库候选。** 完整哈希、来源角色、分音、反向检索和候选前置条件见 [JSON 决策](source-and-rule-decision.json)。

| owner ID | 实际原名 | 已发表 Latin | 保留的姓／名分音 | 规则输出 |
|---|---|---|---|---|
| 6531 | 黃家胤；队列简体为黄家胤 | Huang Jia-Yin | `[[huang], [jia, yin]]` | **황자인** |
| 5115 | 杨以伦 | Yang Yilun | `[[yang], [yi, lun]]` | **양이룬** |
| 5214 | 柯沛辰 | Ke Peichen | `[[ke], [pei, chen]]` | **커페이천** |
| 5543 | 王紫涵 | Wang Zihan | `[[wang], [zi, han]]` | **왕쯔한** |

这是对实际发表的完整拼写逐名作出的普通话／汉语拼音判断。来源没有明写“汉语拼音”，因此不能把该判断冒称为出版者的系统声明，也不能推广成“英文栏就是拼音”。本次不从汉字补读音，不根据国籍或居住地选读音，不增加声调。项目继续合写姓和名，分界保留在证据中。

## 实际来源与判断

- **6531：**[台湾棋院原页](https://taiwangorg.blogspot.com/2022/12/blog-post_91.html)原文第 626 行同段刊出「黃家胤」和「英文名: Huang Jia-Yin」；海峰棋院的独立中文档案也写黃家胤。`huang / jia / yin` 是这组已发表汉字与 Latin 对应下的完整普通话音节；`Jia-Yin` 已明确给出名的音节界。页面是繁体中文夹 Latin，不能整页标作英文，也不能改写原文成「黄家胤」后声称字面命中。
- **5115：**[U-Go /2275/](https://db.u-go.net/2275/)原文第 75、82、103 行给出 `Yang Yilun`、`杨以伦` 和同一排序名。`yang / yi / lun` 分音完整，无须从汉字推导新拼写。GoRatings 同一 `/1604/` 档案佐证原名；其韩文路径仍显示 Latin。此处审核的是该棋手在围棋来源中实际使用的中文姓名，不以现居地排除其原名读音。
- **5214：**GoRatings [中文页](https://goratings.org/zh/players/2480.html)与[英文页](https://www.goratings.org/en/players/2480.html)的标题分别为柯沛辰／Ke Peichen，两者共用 `/2480/`，同生日且同链至海峰档案 `ACBF499C50310A39B5ED50FBD5B1E4E3`。这组精确配对支持 `ke / pei / chen`。GoRatings 是围棋资料库，不能标为官方机构。
- **5543：**GoRatings [中文页](https://www.goratings.org/zh/players/2445.html)与[英文页](https://www.goratings.org/en/players/2445.html)分别刊王紫涵／Wang Zihan，共用 `/2445/` 且同链至海峰档案 `B15AD71345F8FF8D7E2E8FC2D7037F82`。采用已发表的 `wang / zi / han`，不替换成其他可能读法。

## 精确有限新增映射

复用 [NIKL 官方规则](https://korean.go.kr/kornorms/m/m_regltn.do?regltn_code=0003)已保存的完整原文，SHA-256 为 `92977a7c4e2d255aa62d91011372bea1a198f5c3ee6f92db5b02fa6366fb9d9b`。表 5 位于原始 HTML 第 1573 行，括号说明第 1578 行，声调条款第 6666 行，`ㅈ/ㅉ/ㅊ` 后的介音调整第 6707 行。表是一般规则依据，不是 NIKL 对这些个人姓名的背书。

| 新增音节 | Hangul | 表 5 的直接项或审核组合 |
|---|---|---|
| huang | 황 | `h → ㅎ` + `wang (uang) → 왕`，选声母后的 `uang` |
| jia | 자 | `j → ㅈ` + `ya (ia) → 야`；中国语第 2 项明示 **쟈 → 자** |
| yin | 인 | 直接项 `yin (in) → 인`，零声母形式 |
| yang | 양 | 直接项 `yang (iang) → 양`，零声母形式 |
| yi | 이 | 直接项 `yi (i) → 이`，零声母形式 |
| lun | 룬 | `l → ㄹ` + `wen (un) → 원 (운)`，按注选声母后的 `un → 운` |
| ke | 커 | `k → ㅋ` + `e → 어` |
| pei | 페이 | `p → ㅍ` + `ei → 에이` |
| chen | 천 | `ch → ㅊ` + `en → 언`，不套独立音节 `chi` |
| han | 한 | `h → ㅎ` + `an → 안` |

`wang → 왕`、`zi → 쯔` 沿用现有条目；不新增其他音节或通用转写器。

## 有限韩文检索结论

已重算五份资料所引用的身份、读音、Bing/Naver 搜索原文 SHA-256，并补查四个拟议韩文名。来源和工具返回保存在 [检索原始响应](source-rule-contrary-search-transcripts.json)。没有全网不存在、固定网站数或全量消极闭合的主张。现有中国棋手名录也不能充当台湾棋手的穷尽范围；`Ke Peichen` 的一份 Naver 响应含临时错误，只能记作该次不可用。GoRatings 韩文页面的英文回退不能计为韩文刊名。

其中 **5543 不是“从未见过韩文”**：[2024-04-17 Tistory 社区榜单](https://qkrrhkdfo1.tistory.com/640)第 723 行实际写「왕쯔한(王子漢)」，链接正是 `/en/players/2445.html`。直接 GET 的真实原文和哈希已保存于 [capture 记录](source-rule-wang-korean-ranking-capture.json)。韩文与规则结果一致；该社区抄录行的汉字标签与已验证原名不同，不能将「王子漢」解释为「王紫涵」的繁简转换或据此改原名。它属于参考资料中的同名正面命中，未达到官方／专业来源的 conventional gate，不妨碍本次生成规则输入审核。

**5806 蕭睿杉／Wesley Hsiao：hold。** 官方页面的英文别名没有给出「睿杉」的完整普通话读音，`Hsiao` 也不能静默改写成 `xiao`。不批准其音节或输出。

## 候选之前必须诚实解决的现有契约限制

1. 当前校验器强制 `modern_mainland=True`。台湾资料不能虚填；须以单独审核的有限范围更新承载这里认可的现代普通话姓名，保留逐名输入证据要求。
2. 5214、5543 的 Han 与 Latin 分处同档案的两份真实页面。现有单 `reading.capture` 要求一份正文同时包含二者，不能直接装下该证据。必须保留两份正文、各自哈希及同档案链接关系并采用受支持的证明结构；不得拼接后冒称一份 HTTP 原文。未完成时只让相关候选待定。
3. 6531 使用实际繁体原名「黃家胤」。复用 CN/EN 名称时，原名、证据、applied batch 和创建记录须按实际字面绑定；不能强迫简体 CN anchor 等于繁体原名。

本次没有访问数据库、SSH、修改程序或部署。四个物理 verified 名称及 owner 选择沿用任务输入，未冒称做了当前资格复核。最终 KO 空目标、跨 owner 韩文重名、实时来源资格以及精确候选独立签署仍由下一阶段完成。
