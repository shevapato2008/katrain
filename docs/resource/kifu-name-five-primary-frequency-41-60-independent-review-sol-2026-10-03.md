# 频次 41–60 五主语言姓名来源独立复核（Sol）

审核日期：2026-10-03（北京时间）。范围为候选 memo 所列 19 人 × `cn/tw/jp/ko/en` 的 **95 格**，跳过已审核的 Go Seigen。

**原样候选结论：62 PASS / 33 HOLD。** 分语言为 `cn` 7P/12H、`tw` 3P/16H、`jp` 15P/4H、`ko` 18P/1H、`en` 19P/0H。候选 memo 的 66 个字面候选中，4 个日文简体字形尚不满足严格日文用名证据，故仍 HOLD。报告另举证 4 个可供后续选择的新日文候选；它们不改写原候选，不计入 62 个原样 PASS。

PASS 只表示所列精确显示姓名有相应语言来源、且外部资料所指职业棋手的身份语境成立；不批准本地 raw 槽、人物主键、QID、FK、棋谱/专辑归属或数据库写入。GoRatings `/zh/` 不映射为 `cn/tw`；字形繁体也不自行证明台湾来源。`jp` 对应网页 `ja`，`cn/tw` 分别要求简中和台湾繁中直接用名。

## 输入与完整性核验

读取[候选 memo](kifu-name-five-primary-frequency-41-60-candidates-luna-2026-10-03.md)及以下受控目录中的 manifests 和原始响应：

- `~/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/five-primary-41-60-first10-luna/`
- `~/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/five-primary-41-60-second9-luna/`

独立重新计算 **76 份 GoRatings HTML（19×4）和 6 份机构响应**的 SHA-256：全部与 manifest 相符；6 份机构响应的字节长度也全部相符。76 个实际 H1 与候选原样相同，实际 `html lang` 分别为 `en/ja/ko/zh`，每页出生日期行均包含 manifest 的完整生日；19 个 profile 各语生日一致。正文的英文、日文、韩文界面和棋局记录也与相应语言一致。确认目录 0700、已检查 GoRatings 响应文件 0600。未以 manifest 中的 H1 替代网页解析结果。

| 清单 | 重新计算 SHA-256 | 结果 |
| --- | --- | --- |
| first10 `capture-manifest.json` | `92e6c9121d1ba258ab249d1f5898b0cc77961fb618203468934f1fe5cede315c` | 与 memo 相同 |
| second9 `capture-manifest.json` | `231475b4386c219a2701090e12dad9c56deaefb698ce3c84f20a5473eecd0894` | 与 memo 相同 |
| second9 `specialist-capture-manifest.json` | `0204bfd0114249f93fcd371248ff4f205966e7e3783113cccfa8968ee1ece154` | 与 memo 相同 |

GoRatings 多语页是**同一出版方**。同 ID、生日和棋局不能算四个独立来源。CWA 与海峰是两个独立专业出版方，支持本批 10 人的身份；其余 9 人另直接核对日本棋院/韩国棋院个人档案，见后表。官方档案支持所指职业棋手，不自动把 GoRatings 的所有转写升格为各机构统一首选拼写。

## 95 格原样结论

`P=PASS`，`H=HOLD`；`— H` 表示候选包未取得该格的合格直接来源。表中生日是四份 GoRatings 原正文一致的生日，独立机构生日见后表。保留原样空格与异体，包括 `최 정`、`趙漢乗`、`元晟ジン`。每格 GoRatings 页面可精确定位为 `https://www.goratings.org/{en,ja,ko}/players/{ID}.html`，`ja` 对应 `jp`。

| 输入姓名 | GoRatings ID / 原正文生日 | cn | tw | jp | ko | en |
| --- | --- | --- | --- | --- | --- | --- |
| 一力辽 | 1231 / 1997-06-10 | — H | — H | `一力遼` P | `이치리키 료` P | `Ichiriki Ryo` P |
| 河野临 | 182 / 1981-01-07 | — H | — H | `河野臨` P | `고노 린` P | `Kono Rin` P |
| 高川格 | 593 / 1915-09-21 | — H | — H | `高川格` P | `Takagawa Kaku` H | `Takagawa Kaku` P |
| 崔精 | 1223 / 1996-10-07 | — H | — H | `崔精` P | `최 정` P | `Choi Jeong` P |
| 陈诗渊 | 241 / 1985-10-28 | — H | `陳詩淵` P | `陳詩淵` P | `천스위안` P | `Chen Shiyuan` P |
| 赵汉乘 | 99 / 1982-11-27 | — H | — H | `趙漢乗` P | `조한승` P | `Cho Hanseung` P |
| 元晟溱 | 114 / 1985-07-15 | — H | — H | `元晟ジン` P | `원성진` P | `Weon Seongjin` P |
| 范廷钰 | 1194 / 1996-08-06 | `范廷钰` P | — H | `范廷钰` H | `판팅위` P | `Fan Tingyu` P |
| 卞相壹 | 1290 / 1997-01-14 | — H | — H | `卞相壹` P | `변상일` P | `Byun Sangil` P |
| 檀啸 | 995 / 1993-03-10 | `檀啸` P | — H | `檀嘯` P | `탄샤오` P | `Tan Xiao` P |
| 萧正浩 | 572 / 1988-10-05 | — H | `蕭正浩` P | `蕭正浩` P | `샤오정하오` P | `Xiao Zhenghao` P |
| 柳时熏 | 41 / 1971-12-08 | — H | — H | `柳時熏` P | `류시훈` P | `Ryu Si Hoon` P |
| 江维杰 | 964 / 1991-10-17 | `江维杰` P | — H | `江维杰` H | `장웨이제` P | `Jiang Weijie` P |
| 山田规三生 | 65 / 1972-09-09 | — H | — H | `山田規三生` P | `야마다 기미오` P | `Yamada Kimio` P |
| 胡耀宇 | 184 / 1982-01-18 | `胡耀宇` P | — H | `胡耀宇` P | `후야오위` P | `Hu Yaoyu` P |
| 杨鼎新 | 1193 / 1998-10-19 | `杨鼎新` P | — H | `杨鼎新` H | `양딩신` P | `Yang Dingxin` P |
| 唐韦星 | 897 / 1993-01-15 | `唐韦星` P | — H | `唐韦星` H | `탕웨이싱` P | `Tang Weixing` P |
| 连笑 | 1082 / 1994-04-08 | `连笑` P | — H | `連笑` P | `롄샤오` P | `Lian Xiao` P |
| 陈祈睿 | 1534 / 2000-06-15 | — H | `陳祈睿` P | `陳祈睿` P | `천치루이` P | `Chen Qirui` P |

## CWA / 海峰：10 个格的直接独立证据

[CWA 职业名录页面](https://www.weiqi.org.cn/player/professional)为 `html lang="zh-cn"`，保存 HTML 是页面壳，不把其本身冒称为包含 7 人姓名的静态名单。姓名、职业段级和生日来自对应的[职业名单 API](https://wqapi.cwql.org.cn/playerInfo/professional/list) JSON，状态 `code=0`，职业段位分组中各有唯一对应项。API 无 HTML 语码；其简中内容、所属机构与对应页面共同支持 `cn`。独立生日均与 GoRatings 相符。

| 原姓名 | CWA 原字 / 编号 | 原段级 | API 完整生日 | cn |
| --- | --- | --- | --- | --- |
| 范廷钰 | 范廷钰 / CWA000036 | Z09 | 1996-08-06 | PASS |
| 檀啸 | 檀啸 / CWA000018 | Z09 | 1993-03-10 | PASS |
| 江维杰 | 江维杰 / CWA000019 | Z09 | 1991-10-17 | PASS |
| 胡耀宇 | 胡耀宇 / CWA000025 | **Z08** | 1982-01-18 | PASS |
| 杨鼎新 | 杨鼎新 / CWA000062 | Z09 | 1998-10-19 | PASS |
| 唐韦星 | 唐韦星 / CWA000040 | Z09 | 1993-01-15 | PASS |
| 连笑 | 连笑 / CWA000052 | Z09 | 1994-04-08 | PASS |

海峰[职业棋士名录](https://www.haifong.org/profession)及三份个人页实际均为 `zh-tw`，名录列三人九段；个人页正文直接写姓名、生日、出生地、入段/升段与职业棋战履历。名录和个人页仍只有海峰一个出版方。蕭正浩个人页路由是 `/venue/`，其可见档案放在精锐队/道场栏目；正文职业段位和入段履历明确，因此不因路由名称拒绝职业身份，也不把路由误报为 `/profession/venue/` 的当次抓取。

| 原姓名 | 台湾直接用名 / 个人页 | 独立生日 | 职业身份语境 | tw |
| --- | --- | --- | --- | --- |
| 陈诗渊 | [陳詩淵](https://www.haifong.org/profession/venue/248B7B2EE622C94D9B841530AE46D9FF) | 1985年10月28日 | 九段；2000韩国棋院入段、2005移籍台湾、2011九段 | PASS |
| 萧正浩 | [蕭正浩](https://www.haifong.org/venue/24FA409B34B5EDEB5AA85CD9CA4234E5) | 1988年10月5日 | 九段；2001入段、2014九段及台湾职业棋战履历 | PASS |
| 陈祈睿 | [陳祈睿](https://www.haifong.org/profession/venue/E0105F37B8050597F275972467EA648E) | 2000年6月15日 | 九段；2013入段、2025九段及职业棋战履历 | PASS |

机构原响应 SHA-256 已全部核对：

| 响应文件 | SHA-256 |
| --- | --- |
| CWA API | `18ba2a04efdca69d47528cbe703d9c54e1005b7f986af782434cbc3f1dd316f9` |
| CWA 页面壳 | `f1a3a731ea968b580252ecec12c3f3f770b63d605be95d302d6bfd527449396b` |
| 海峰名录 | `9e637408d3571ae9041b03eea07a2e2cf2baf3ed0dd480f15c25ea36955d3163` |
| 海峰蕭正浩 | `03d87d2bbd7bdf21a2d5aeee8a29bdc27e5eafbed4163db39ceca7f6010838a8` |
| 海峰陳祈睿 | `6a117c55e52b1e33a75eb3b9c0bce4f2bcbcc0436e311d3abe60ca5dca053ed3` |
| 海峰陳詩淵 | `5c98c55a96dd26aec4886f91ff93d7ad9834e46eb0f7ec05597966734702c0af` |

## 其余 9 人：独立职业身份核对

以下原包 GoRatings 英文页实际链接到对应官方档案；审核时直接 GET 官方响应，实际语码为日本棋院 `ja`、韩国棋院 `ko`，所有日期均与原包完整生日相符。日本棋院有一个空 logo H1及一个非空姓名 H1；下表记录非空姓名，而不是把 logo 或网页 title 当作姓名 H1。韩棋院正文为 `기사정보 상세`，直接列姓名、九段、所属韩国及出生日期。

| 输入名 | 独立个人档案 / 页面姓名 | 独立完整生日 | 职业语境 |
| --- | --- | --- | --- |
| 一力辽 | [日本棋院](https://www.nihonkiin.or.jp/player/htm/ki000435.html)：`一力　遼`，`ICHIRIKI, Ryo` | 1997-06-10 | 九段、东京本院、2010夏季入段 |
| 河野临 | [日本棋院](https://www.nihonkiin.or.jp/player/htm/ki000345.html)：`河野　臨`，`KONO, Rin` | 1981-01-07 | 九段、东京本院、1996入段 |
| 高川格 | [日本棋院](https://www.nihonkiin.or.jp/player/htm/ki001043.html)：`高川　格`，`TAKAGAWA, Kaku` | 1915-09-21 | 九段、22世本因坊秀格；1986逝世 |
| 崔精 | [韩国棋院](https://www.baduk.or.kr/record/player_view.asp?pkey=10000580)：`최 정( 崔 精 )` | 1996-10-07 | 九段、韩国、女子职业棋士奖项及升段履历 |
| 赵汉乘 | [韩国棋院](https://www.baduk.or.kr/record/player_view.asp?pkey=10000108)：`조한승( 趙漢乘 )` | 1982-11-27 | 九段、韩国、职业升段及亚运履历 |
| 元晟溱 | [韩国棋院](https://www.baduk.or.kr/record/player_view.asp?pkey=10000144)：`원성진( 元晟溱 )` | 1985-07-15 | 九段、韩国、权甲龙门下及职业升段 |
| 卞相壹 | [韩国棋院](https://www.baduk.or.kr/record/player_view.asp?pkey=10000700)：`변상일( 卞相壹 )` | 1997-01-14 | 九段、韩国、2012职业入段及职业奖项 |
| 柳时熏 | [日本棋院](https://www.nihonkiin.or.jp/player/htm/ki000277.html)：`柳　時熏`，`RYU, Si Hoon` | 1971-12-08 | 九段、东京本院、1988入段 |
| 山田规三生 | [日本棋院](https://www.nihonkiin.or.jp/player/htm/ki000292.html)：`山田　規三生`，`YAMADA, Kimio` | 1972-09-09 | 九段、关西总本部、1989入段 |

官方档案中的姓名排版空格、逗号及大写拉丁转写是其实际形式；GoRatings 的 `Ichiriki Ryo` 等 PASS 仍限定于 GoRatings 原样显示，并非声称官方 H1逐字使用同一串。`ko`中崔精的 `최 정` 保留实际中间空格，不静默改写为 `최정`。

| 官方当次 GET 响应 | SHA-256 |
| --- | --- |
| 日本棋院 ki000435 | `f95f60154f267d6c5abed5d4778e0ffa1cf35c35143ad6ca4c10f763f850a6e5` |
| 日本棋院 ki000345 | `7ec50a11d9833b24593b3f380fc808a7239f27cd31140c2a00c96b15b09c0dd7` |
| 日本棋院 ki001043 | `9b4f1a698616233b348cc9c655b927328810de358a01adeb3c837af1fc798511` |
| 日本棋院 ki000277 | `2af4cc4befd690dec35ff4fa716020da7dce327ed7953cd8dd4e2b5d5f8a3f0e` |
| 日本棋院 ki000292 | `c8299ee05fbc6f4b15ad85d4f53b911d4b29338222a1fc98a89c357a501666c6` |
| 韩国棋院 pkey=10000580 | `8bdff8aca6fde0e28f78afa7cc9d3d2f4c80cff0c5223f8b6d4f4af1dc31a6c5` |
| 韩国棋院 pkey=10000108 | `e1feffae4109edd9d465c2243e7fd597edda637ab542b41ccdf9f7d71161897b` |
| 韩国棋院 pkey=10000144 | `30de53f10c6880386d91f03d363ac880c68127184dbc8bb320040c693cb9989b` |
| 韩国棋院 pkey=10000700 | `09c6c1ce9bdfbd4b9587640a568c8b8b932dd88561519c999117bb6e37724542` |

这些新增网页只直接读取并在本报告记录响应哈希；遵守“只写指定报告”，未额外保存 raw 响应或创建新 manifest。因此它们不是声称已经加入原受控证据包的持久化快照。

## 语言边界与必要修订

### 4 个 jp 原候选 HOLD；新候选原文已找到

`范廷钰、江维杰、杨鼎新、唐韦星` 都确实出现在 GoRatings `ja` H1，但相应简体字的日文职业使用未得到独立印证。不能仅凭 `lang=ja` 批准 fallback 字形，也不能自动转换后称原源文字。

日本棋院[2014年3月第3周对局结果](https://archive.nihonkiin.or.jp/match/2014/03/33_17.html)（正文 `ja`；非空标题为 H2，logo H1为空）直接写以下替代形式，均为 **2014-03-18 百霊杯一回战**。原包英文棋局行逐项匹配日期、对手、手番与胜负，故是对应职业棋手的新显示候选，而非泛泛同字姓名：

| 原 jp 候选 / 原样结论 | 可提议新 jp 候选 | 日本棋院实际表格原字 | 原包英文页同日记录 |
| --- | --- | --- | --- |
| 范廷钰 HOLD | 范廷ギョク | `范　廷ギョク 九段`，黑2目半胜韩雄奎 | ID1194 `Black Win Han Wonggyu` |
| 江维杰 HOLD | 江維傑 | `江　維傑 九段`，黑中押胜党毅飞 | ID964 `Black Win Dang Yifei` |
| 杨鼎新 HOLD | 楊鼎新 | `楊　鼎新 三段`，黑中押胜张立 | ID1193 `Black Win Zhang Li` |
| 唐韦星 HOLD | 唐韋星 | `唐　韋星 九段`，黑负毛睿龙 | ID897 `Black Loss Mao Ruilong` |

新候选只移除棋局表姓名排版空格，未转换字形或音译。该官方响应 SHA-256为 `f4a7c29a68f42e653c2429eef2988744915f9e458ef3103f8a238b2b292035e2`。这些新候选可 PASS 为明确来源显示；如另开修订包采用四项，届时可为 **66P/29H**，本原候选表仍是 **62P/33H**。不把 `范廷ギョク` 改称自动汉字转换后的 `范廷鈺`；后者需自己的直接原文。

### 元晟ジン原 jp 候选 PASS：混写确有日文职业直接用例

日本棋院[第16回三星杯](https://www.nihonkiin.or.jp/match/sansei/016.html)实际正文直接写 `元晟ジン`，历史第16回区块列其2011年决赛对古力三局：12月5日白胜、6日黑负、7日黑胜，与 ID114 原包三条英文棋局行逐项相符。因此不是仅凭日文界面批准混写。该 URL 顶部还有当前第30回区块，身份连接明确使用**历史第16回区块**，没有把2025年的现行结果误当2011年证据。当次 SHA-256：`d2bfdd5428f9bf13a91d40eeb4309b7ccb95c353d050184bf13eff291d10c130`。

### 高川格 ko HOLD：语言界面不补足韩文姓名

页面实际 `lang=ko` 且韩文正文，但 H1 为 `Takagawa Kaku`，没有韩文字母。因此仅 `en/jp` PASS，不把这个拉丁 fallback 算成韩文姓名。最窄补证方向为韩国棋院或韩国专业围棋史正文直接使用其韩文全名，并以1915-09-21、22世本因坊秀格或本因坊九连霸职业履历连接同人；不得自行音译生成替代格。

### 28 个 cn/tw 缺来源格：维持 HOLD

- **cn 12 格**：一力辽、河野临、高川格、崔精、陈诗渊、赵汉乘、元晟溱、卞相壹、萧正浩、柳时熏、山田规三生、陈祈睿。最窄方向为中国围棋协会或中国职业赛事简中正文直接用名，并用具体赛事日期/对手/结果或职业生日连接身份。输入姓名只是查找线索，不能当成已获简中证据。
- **tw 16 格**：一力辽、河野临、高川格、崔精、赵汉乘、元晟溱、范廷钰、卞相壹、檀啸、柳时熏、江维杰、山田规三生、胡耀宇、杨鼎新、唐韦星、连笑。最窄方向为海峰/台湾棋院的单篇国际赛事正文或职业史专栏，直接摘取台湾实际姓名并核对赛事/职业身份。可先找同一篇包含多人名单的文章，保持逐人职业语境；未取得前不从 GoRatings `/zh/`补格。

原包19份 `zh` H1仅作为原中文页证据留存。无论简繁、是否和输入名同字，都不额外计入本次 `cn/tw`，也不作为独立出版方。

## 完成边界

本报告逐格审核95格来源姓名，未评估本地库存覆盖率或 raw 槽适用性。只写此报告；未改代码、候选 memo、受控包、来源 registry、数据库或任何 FK，未提交。
