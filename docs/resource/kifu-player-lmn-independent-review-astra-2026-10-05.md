# L / M / N 棋手五语名称独立语义审核

Reviewer: `/root/link407_review_astra` (`gpt-6-astra`); producer: `/root/event10_review_apply` (`gpt-6-astra`).

结论：三批各 25 项语义及来源通过。N 王磊韩文显示已清理消歧后通过；全部候选仍 pending，未填写 reviewer 签名、未生成 approved bundle、未写数据库。最终签署及目标库 stale/collision 检查由主线程完成。

## 检查范围与结果

- 实读 75 个显示值对应的来源标题/人物正文及 15 位棋手的官方身份锚点；70 个 Wikipedia 条目的实际 h1、真实正文节点、HTML 中 wgRevisionId 与保存的 article_evidence 一致。其余 5 项直接使用专业档案或棋院本人页。
- 两环境研究/候选 hash、owner/lang/display 绑定、每包 5 个 owner 及 25 个 pending 候选、零 album_links 均一致。93 个被研究引用的唯一正文文件逐个 SHA-256 通过，另核对 L 留存 CWA roster 的正文 SHA 及两个人物行。
- 6 个现有 CLI validate 全部重新执行：每包 pending=25、missing=0、errors=[]、write_errors=[]；ready/write_ready 为 false 是缺正式签名的预期结果。

## 重点语义决定

### L：许皓𬭎及生日差异

- `许皓𬭎` 的末字为 U+2CB4E，确实出现在[简体维基](https://zh.wikipedia.org/zh-hans/%E8%A8%B1%E7%9A%93%E9%8B%90)的标题和人物正文。繁体/日文为許皓鋐，[海峰棋院本人档案](https://www.haifong.org/venue/498745583367139F2AD618F39303A6C4)以姓名、2001-04-30、职业履历及杭州亚运个人金牌核实同人。接受实际出版字形，不改成推测拼写。
- 谢赫的[韩国棋院档案](https://m.baduk.or.kr/record/gisa_info.asp?PRPL_CODE=10000359)记 1984-05-04；五语 Wiki 及留存 CWA000512 记 1984-05-14。原名謝赫、曹大元门下、2002全国个人赛冠军、2003三星杯四强及2012农心杯战绩共同确认职业棋手身份，没有混入同名古代画家。生日仍未裁决，不写 DOB。L 摘要的官方链接旁已改成分别列出两种日期。
- 党毅飞的[韩国棋院档案](https://www.baduk.or.kr/record/player_view.asp?pkey=20000536)和留存 CWA000064 为1995-06-17，中文/日文/韩文 Wiki 与 GoRatings 为1994-06-17。原名黨毅飛/당이페이及2012 BC Card 决赛履历足以确认同人；日期差异已在原研究记录保留。英文使用[GoRatings 1135 本人页](https://www.goratings.org/en/players/1135.html)，经同 ID 中文页核同人。
- 林立祥 cn/en 来自[GoRatings 1533](https://www.goratings.org/en/players/1533.html)，tw 来自[海峰本人页](https://www.haifong.org/profession/venue/CFE91E4CC316BDAA23077D2D414DA825)。中文页面周边确为简体，林立祥本名无简繁字符差别；日/韩人物条目与官方姓名及1993-09-07一致。L 的25项 payload/hash未改。

### M：秀哉和邱峻

- [日本棋院殿堂页面](https://www.nihonkiin.or.jp/profile/sisetsu/dendou/list05.html)在秀栄段落之后明确另列「21世 本因坊秀哉」，本名田村保寿、1874–1940，四国语言人物条目与两种中文变体均对应此人。未把同页的17/19世本因坊秀栄作为目标。
- 邱峻额外发现生日异文：KBA/中/韩记8月22日，日文8月27日，英文8月24日，出生年均1982。职业姓名邱峻、上海棋手、1995入段及世界赛履历明确同人。初步口头更新称研究声称日期一致，细读实际 payload 后确认其仅称姓名和职业身份一致；因此未改25项候选及研究 hash，只给 people/source-map/decision summary 补上生日差异。
- 邱峻韩文页标题 `추쥔` 与[韩国棋院原名](https://www.baduk.or.kr/record/player_view.asp?pkey=20000015)一致；正文首句也出现另一写法 `치우쥔`。没有明确“技术标题不准确”说明，依用户允许直接采用 Wikipedia 标题的规则保留 `추쥔`。
- 李轩豪韩文人物首段是实际 li 节点，独立核对原始 HTML 与 passage/hash 一致；其余藤泽里菜、芝野虎丸五语均与各自日本棋院档案及本人条目相符。M25项候选/研究hash未改。

### N：王磊消歧与新增官方来源

- [王磊韩国棋院档案](https://www.baduk.or.kr/record/player_view.asp?pkey=20000007)为王磊/왕레이、1977-12-26、中国八段、2002三星杯亚军。中/日/韩/英人物正文均为同人；没有选用另一位王雷。
- 韩文显示由 `왕레이 (1977년)` 改为正文姓名 `왕레이`。完整[原页面 URL](https://ko.wikipedia.org/wiki/%EC%99%95%EB%A0%88%EC%9D%B4_(1977%EB%85%84))、实际标题 `왕레이 (1977년)`、revision 41395491、捕获正文 bytes/hash 不变；article passage 改为原始正文中的真实首段，重算 passage 与研究 hash。仅 N 的这一语言显示项改变，两环境各1项；members/owners/前像/FK不变。
- 村川大介对应[关西棋院本人档案](https://kansaikiin.jp/kisi_prof/murakawadaisuke.html)，1990-12-14、森山直棋门下，五语职业身份一致；英文条目实际标题为 `Murakawa Daisuke`，请求 URL 的重定向名字不覆盖实际标题。
- N registry 相比 M 仅改 version/description，并新增 `kansai-kiin`（official、ja、https://kansaikiin.jp/）；既有来源与 language_scopes 均未改，接受这项有原始官方档案支持的扩充。registry canonical SHA：`ccdc63d80c83198bea542dd8eaf404ee6cfe9b2296a4e41edee5094a9a5abd4d`。
- 赖均辅英文 `Lai Junfu` 取[GoRatings 1706 本人页](https://www.goratings.org/en/players/1706.html)，同 ID 中文賴均輔及海峰官方2002-04-08锚点相符。其余赵善津、王檄五语均为本人。

## 最终 pending bundle hashes

| Group | Environment | SHA-256 |
|---|---|---|
| L | PROD | `1ad94845df86f620732738a92675387130b4f0d245d26dc896f9d2e76d80aead` |
| L | TEST | `59c796f31f0354717957c8b17b79b8015606e6c1accd69874f9bcd22baff4d16` |
| M | PROD | `5637ee8e24881e785ddfa7f9441a6e1b9fc09e268c91b42633c4ec6ecb811229` |
| M | TEST | `c081ccd9357a35681f8ef846361ee8cbafb541b3fc42d70e61a849dd25addd73` |
| N | PROD | `fc049424494ffe17d628595923c158def2fcb0bfa448e3f8b866e89ad367ceef` |
| N | TEST | `3c0ff3bdbf3251b7ffb93c28c306c8e1472464637da814011e2b20d30f5181ef` |

各包目录为 `/tmp/kifu-player-next5{l,m,n}-20261005`。N 请使用本表新 hash，勿继续使用消歧清理之前的 pending hash。
