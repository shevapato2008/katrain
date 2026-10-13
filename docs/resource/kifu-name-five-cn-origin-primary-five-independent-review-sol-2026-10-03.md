# 五名中文棋手：主五来源独立审核与胡耀宇签锚 HOLD

2026-10-03；独立 reviewer `/root/freq41_60_95_review_sol`，GPT-6 运行时身份，未独立认证子型号。审核 [Luna 候选](kifu-name-main-five-candidates-luna-2026-10-03.md)及冻结正文；未修改生产者或旧签名，DB 连接／写入、应用代码修改、Git 提交均 0。

**25 格来源姓名／专业人物对应事实 PASS；候选 crosswalk 20 格通过来源核对、胡耀宇 5 格依赖 HOLD。** 本次签署仅限来源事实；不签可执行 candidate bundle，不新增 raw applicability、人物 FK、别名或写库授权。

## 逐格来源事实

表中每个单元均为 **PASS**，不是数据库显示批准。

| 原名 / GoRatings ID / DOB | cn | tw | jp | ko | en |
| --- | --- | --- | --- | --- | --- |
| 唐韦星 / 897 / 1993-01-15 | 唐韦星 | 唐韋星 | 唐韋星 | 탕웨이싱 | Tang Weixing |
| 杨鼎新 / 1193 / 1998-10-19 | 杨鼎新 | 楊鼎新 | 楊鼎新 | 양딩신 | Yang Dingxin |
| 檀啸 / 995 / 1993-03-10 | 檀啸 | 檀嘯 | 檀嘯 | 탄샤오 | Tan Xiao |
| 胡耀宇 / 184 / 1982-01-18 | 胡耀宇 | 胡耀宇 | 胡耀宇 | 후야오위 | Hu Yaoyu |
| 连笑 / 1082 / 1994-04-08 | 连笑 | 連笑 | 連笑 | 롄샤오 | Lian Xiao |

- 五人 CWA 唯一姓名行、稳定 ID、完整 DOB 与 GoRatings `/zh/` 身份桥及同 ID `/en/` 一致。逐格候选值和 body hash 与已审 95 格修正版一致；所用 18 份不同正文及 5 份 `/zh/` 身份桥重新读取核对。修正版 sources manifest 全部 80 份正文哈希亦吻合。
- cn 为协会实际简体名录；tw 为海峰 `zh-tw` 页面中的真实繁中赛事／冠军姓名，不由转换器生成。唐／杨 jp 来自日本棋院 `ja` 表格的 `唐　韋星`／`楊　鼎新`，只删姓名内部排版全角空格；2014-03-18 对手、黑方与胜负分别吻合同 ID GoRatings 历史。其余 jp、全部 ko/en 是实际目标语 H1、目标语正文与同 DOB；唐／杨 GoRatings-ja 简体 H1 未冒充这两个日文候选。
- 候选 JSON 字节 SHA-256 `64e891f5f3f2cae426b652dc6287af783662c0e91731b0d7b81a43776bf77d7f`，所有所列依赖哈希吻合。旧捕获缺逐页时间者不补造时间。
- 独立已签 scope 的完整 record hash、每槽 11 个 context、原名及 NULL FK 与冻结 inventory 的精确成员集合相同：858／864／911／868／857，共 **4,358**。此核对保留既有显示范围，不把姓名、日期或来源人物对应升级为棋谱人物归属；FK 批准仍 0。

## 胡耀宇：错误定位的精确边界

实际 CWA JSON：`five-primary-41-60-95-aux-span-corrected-root/sources/weiqi-association-18ba2a04efdc.json`（受控目录根见下文）。字节 SHA-256 **`18ba2a04efdca69d47528cbe703d9c54e1005b7f986af782434cbc3f1dd316f9`**。全响应唯一行位于 **`data.Z08[10]`**：`playerNo=CWA000025`、`playerName=胡耀宇`、`playerGrade=Z08`、`playerBirthday=1982-01-18`。`Z09` 中没有该人物。

最新已签锚 `five-cn-origin-v3-scope-rebound-anchors-approved-sol/raw-anchors-v3.approved.json` 的胡耀宇 `source_anchor.content.sources[0].record_locator` 却为 `data.[Z09] roster row playerNo=CWA000025`。同 record 的 body_excerpt 已写真实 `Z08`，故这是错误定位陈述，不是姓名／ID／DOB／英文读音或来源字节失真。该锚 **HOLD，停止下游复用**：

- 旧 anchor content SHA：`3e2f1284091b9220f2bf8017bac8d88fac1df0e8c3406effd644cd2bc7ee8cd8`。
- 旧完整签锚 SHA：`511c54aaa004a0262537ca9685caa457c39e3edd5f1a7045f553a3578977f74c`。
- 主五 pending JSON 的胡耀宇五行 `identity_crosswalk.official_cwa_record_locator` 仍为错误 `Z09`，并引用旧完整签锚 SHA；虽然公共候选表已经写对 `Z08[10]`，**这五行 crosswalk 仍 HOLD**。

其他四人实际定位是 `data.Z09[43]`／`[58]`／`[41]`／`[21]`，各自正文摘录、ID、DOB、content／完整签锚哈希吻合；其原签锚独立有效，无需因胡耀宇错误重签。五份 raw scope、五份 category approval、六份语言 rule 均不依赖该错误 locator，可保留原字节与审批；25 格直接来源事实及旧 95 格来源事实不因此失效。

## 六语包与克隆记录的资格影响

`five-cn-origin-v3-final-batches-approved-sol/bundle.reviewed.json` 字节 SHA **`7457dfdf43a8c5ed647fcfddc51f4996b9d537229e9d08720a5770d6201e5cfd`**，canonical SHA **`6a13b7e5ff51872d1cbb0310d0847c37b46c5f5f2c4b1f866c97563d88fa9ac0`**。六个 `de/es/fr/ru/tr/ua` batch 每个均包含胡耀宇旧完整签锚 hash，因此 **六 batch 与最终包下游复用 HOLD**，不能继续以旧 `write_ready` 或克隆 PASS 证明其证据合格。

修复胡耀宇锚会改变六个 batch content／完整签署 hash；六个胡耀宇 candidate 需换 anchor hash，**其余 24 个 candidate 也必须换共享 batch hash并取得新批次最终审核绑定**。不是只改胡耀宇六行即可。原 30 个显示字符串仍可保留；胡耀宇直接涉及 868×6＝5,208 槽语格，其余 3,490×6＝20,940 格的来源／规则事实未被否定，但旧共享批次不能拆成新的有效审批。

`five-cn-origin-v3-final-clone-rehearsal-sol/manifest.json` SHA **`bc7f9227ccf5a619f8dc80973c353dcc164769cddec7ea2942375b87e652d0cc`** 及其文件哈希吻合。历史 dry-run/apply/replay/undo、26,148 格运行时表现和撤销恢复记录保留为真实旧输入上的行为记录；**其完整合格包结论不能继续引用，也不能移用到修复后新 hash**。软件哈希／签名检查成功并不证明错误正文 locator 正确。本次未重跑、连接或改动克隆。

## 最小安全修复顺序

1. 生产者复制新版本，只纠正胡耀宇原始 source locator 为 `data.Z08[10]`（保留 ID／DOB 条件、原正文及 capture 时间），记录真实修订者和新时间；旧历史包留存。
2. 独立逐字复验并重签**胡耀宇这一锚**，更新 anchor-record bindings／集合 manifest；其他四个签锚、scope、category、rule 原样复用。同步修订主五 JSON 的胡耀宇五行 locator／新签锚依赖并重算该候选文件 hash。
3. 新六语证据 sidecar／anchor 集合替换胡耀宇锚，六 batch 重绑并独立重签；30 candidate 更新 exact batch approval/hash，六个胡耀宇行另更新 anchor hash。重算各集合／bundle／manifest，保留未变成员及输出，不套用旧签名。
4. 实际目标新鲜只读 inventory/catalog/owner/name preimage/snapshot 校验；若发生前像重绑，独立最终审核须晚于该次真实绑定。通过 validator 后，在另获授权的隔离克隆对**新最终包**做一次聚焦 dry-run/apply/replay/conditional undo 与显示／搜索／覆盖核对，形成新回执。无须重抓已保留来源、重审四个未变锚或扩大 code 测试。

## 独立冻结记录

新独占目录 `~/.local/share/kifu-name-audit/2026-10-03/main-five-primary-five-independent-review-sol/`（0700、文件0400）。`source-decisions.approved.json` 真实签署仅覆盖 25 格来源事实；content SHA **`05ff9432826162256bd558c1a3b4f5c4c7e5df9f47ddd1fb859357bbf5358ceb`**。`review-record.json` 保存每格 candidate canonical hash、实际源路径／hash／语言／跨度、完整身份及 scope hashes、受影响六 batch 与30 candidate精确旧 hashes及资格边界。

上文 `five-…` 路径均相对于 `~/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/`；克隆目录相对于同日审计根。没有改写任何旧 PASS 文件；本 memo 是发现新错误后对旧下游资格的明确补充 HOLD 记录。
