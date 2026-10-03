# 五位中国棋手主五语与全十一语候选包：producer pending

日期：2026-10-03。Producer：`/root/anchor_format4_impl_sol`。本记录不构成独立审批。

## 当前产物

受控目录：`~/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/five-cn-origin-main11-wikipedia-rebound-pending-sol/`。原包完整保留在 `input-main11-v1/`；全部 75 个 manifest 文件已逐一核对 SHA-256，无不匹配。

| 文件 | SHA-256（文件字节） |
| --- | --- |
| manifest.pending.json | 41f0fcd3a617c57bdaaa7d63fced0374e56e1dbb40f8c4a54b71146df694c1c0 |
| bundle.primary-five.pending.json | 4060c01edee84227a3cfc88bb77b3a0370a29940a90827fc606442c2c3e9ba55 |
| bundle.all-eleven.pending.json | b1d21890942f6765d0843d90157705c522f77b18eea41eeb7e9406d8c8b41a92 |
| research.primary-five.pending.json | 539e21aaecba7565bf0e9f9b8f3f67c1a9bda16c7270134e4745ddccd841cb8d |
| candidates.primary-five.pending.json | a3f74f82c432d935346c6a56b20b2bf21ceac02277471e4ee6b742cd38ede3b9 |
| producer-record.json | 54ec091d8b8678685cf4282f41133f1195f97dde6bdb425863729ffdc05cbc75 |

全十一语 bundle canonical SHA：`ba55125b1ec36147e7b4e63145ea8ca24b99fd6a7766e258eaa6f8be4c844deb`。其余完整文件清单与哈希见 manifest。

## 来源与有限变更

25 条主五语 research 和 pending candidate 分别通过实际校验；所有显示字符串保持原值。胡耀宇使用已独立签署 corrected anchor `c4a9f2341449c7d4586718e30dcc4895c0ebf809645a50e7868df49bd2a63172`，CWA 真位置 `data.Z08[10]`。其余中文 locator 均使用原始 JSON 的真实行位置，详见逐条 research。

15 行缺时来源找到同 URL、同 body SHA 的真实旧 capture receipt；另作 9 次实际 HTTP capture（8 个 GoRatings 页面与 1 个日本棋院比赛页），保存状态、真实时间和原始 body。杨鼎新日语使用日本棋院页面真实无空格「楊鼎新」，未增加字符归一化规则。

按用户指定，唐韦星日语改选实际日语 Wikipedia 页面标题「唐韋星」：HTTP 200，fetched_at `2026-10-03T03:31:14.452433+00:00`，revision `103506819`，原始 HTML SHA `bcf4a67f0668716bee4e3ba35fe18eb3d7147d7e204d4d0a149b63f7fff4c4c8`。实际 H1 为无空格标题；日文导言描述中国围棋棋士、1993年1月15日，另以 CWA000040 / 唐韦星 / 1993-01-15 原始官方数据独立 corroboration。摘录来自连续原始 HTML，未合成正文。固定 oldid 链接用于修订引用，不声称另一次抓取。其他 24 条来源选择未因新 Wikipedia 优先政策重做。历史证据均保留。

Pending registry 保留全部旧 entries，只新增实际 CWA API source `cwa-professional-api-cn`：host `wqapi.cwql.org.cn`、精确路径 `/playerInfo/professional/list`、cn 与五 raw scope。版本 `2026-10-03.cn-five-api-pending-v1`，canonical SHA `9982bac257df241d5982b0ea67490aab61a11953dff6932a26af8366a756a553`，字节 SHA `51b3e3397aa3e2a3fb9ea3bbc3b550ab4fcf966ca628bba40b49f531156cd684`。新增项仍待独立审核；没有放宽 host validator，也不把附加声明字段冒充新增运行时强制能力。具体差异见原包 registry-diff.pending.json。

## 实际校验与 HOLD

主五语：25 pending、0 approved、missing 0、rejected 0、write_errors 0；完整 bundle 的 5 个错误是新 raw owner 尚缺 approved display decision。全十一语：55 行，25 pending、30 approved、missing 0、rejected 0；相同 5 个审批闸门错误，另有 30 个次六语前像绑定 chronology 错误。两包 `ready=false`、`write_ready=false`。

原因：真实新绑定时间 `2026-10-03T03:34:54.904919+00:00` 晚于六语既有 batch 审批时间。保留真实时间与既有签名，未倒填或自签。已签五锚、五 scope/category、六 rule、六 batch 内容和所有输出、成员、owner/raw 均保持不变；合包没有 album link、FK、alias 或身份范围扩张。

最短后续路径：独立批准新 registry、25 条主五语来源/候选，最终审核须晚于当前前像绑定；六 batch 的已审来源、rule、成员、输出内容可复用，但其最终 approval records 必须由独立 reviewer 在新绑定后重新完成，再把 30 条候选绑定到新的完整 signed batch SHA 与真实 reviewer 字段。当前旧 signed batch 记录不能直接满足此次新绑定的写入时间闸门。

实际 dry-run 已调用并诚实拒绝 pending display 闸门；SQL writes 0，未调用 apply。

## Clone 与边界

独占 fresh clone `kifu-five-main11-pending-sol-20261003` 从停止的历史 clone volume 复制；未声称当前生产快照。端点/数据库标识维持签署 inventory 的原值：`127.0.0.1:55439/kifu_raw31_clone_20261003`。repeatable-read readonly 重采证明 inventory canonical SHA `f4907ffbe70d62b4b77f6d3bf5ba7ed789f2685f46eff7ffdfe080f2abc4bab1` 与 catalog SHA `37ab4773652e10e38cdcc49a6fc13e3f72ec734aeb30be548d2597c0660f7f09` 不变；五 owner/name 前像均为空。真实 producer、capture、冻结时间保存在受控记录。

clone 已停止，docker inspect 为 exited、Running=false。无 live test/prod 连接、DB apply、应用代码修改、最终自审批准或 Git 提交。
