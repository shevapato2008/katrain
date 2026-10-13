# 胡耀宇修锚后终审候选：真实前像时序 HOLD

2026-10-03；producer `/root/anchor_format4_impl_sol`，GPT-6运行时身份（未独立认证子型号）。承接[六批独立签署PASS](kifu-name-five-cn-origin-hu-batches-independent-review-sol-2026-10-03.md)，新版本 `hu-final-candidates-pending-v3`。没有最终自签、DB apply、部署、应用代码修改或Git提交。

独占目录：`~/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/five-cn-origin-hu-final-candidates-pending-sol/`，目录0700、文件0400。真实新包producer／时间在producer-record和manifest；候选的producer/reviewer字段按代码要求继承实际已签batch字段，不能改写为本轮包组装时间来冒充重新签署。

五锚、五scope/category、六rule及六新已签batch依赖原样复用。30 secondary candidates全部重绑完整已签batch hash及实际batch reviewer、reviewed_at、conclusion字段；胡六行用新完整已签锚 `c4a9f2341449c7d4586718e30dcc4895c0ebf809645a50e7868df49bd2a63172`。显示字符串、成员、owner/raw、rule、scope及name_preimage=NULL语义逐值不变。主五25候选另置独立文件，胡五行已绑定新已签锚；它们仍待单独candidate批准，没有混入六语bundle。

## 独占克隆与实际校验

只读复制原已停止容器 `kifu-raw31-clone-20261003` 的volume到新独占volume／container `kifu-hu-final-pending-sol-20261003`，使用独占端口127.0.0.1:55439。未启动、连接或改变源容器，没有连接live test／prod。新clone是**历史撤销恢复状态的副本**；本轮“新鲜”只指从该副本重新读取时点，不宣称当前生产状态。PG启动的内部恢复不属于应用业务apply；SQL会话强制transaction_read_only，并安装SQL mutation拒绝钩子，实际SQL业务写入0。独占新clone已停止，receipt记录为false。

实际重读inventory完整hash等于原范围inventory；catalog hash相同；approved-name snapshot为空；五个raw owner及其name查询均为空，name preimage仍为NULL。新capture／bound_at均为本轮真实时间。源clone的历史前像材料没有复制成新的时间或签名。

**实际完整validate_bundle：ready=true、approved=30、write_ready=false，30项write_errors。** 六语name decisions的approved状态来自真实已签batch，最终前像绑定审批未成立。全部write_errors为 `preimage binding identity, value or chronology invalid`，原因是新bound_at晚于现有batch reviewed_at。实际dry_run_bundle被调用，并由写入资格门禁拒绝：`bundle name preimages are not write-ready`；没有跳过检查、伪造write_ready，也没有进入apply。

## 最短修复路径

原前像bound_at=01:58早于新batch produced_at=02:37，旧绑定不能合法复用；本轮真实绑定又晚于新batch reviewed_at=02:41，故现有batch签名不能代签后来才形成的前像。

先由独立binder复核并绑定本轮新鲜前像；然后独立最终审核必须晚于该实际绑定。**现有六batch内容、来源、成员、输出、规则及其本轮内容PASS可完整复用，无需修改content或重抓来源。** 但现有运行时代码强制candidate逐字段继承batch producer/reviewer/reviewed_at，因此为使最终前像绑定获批，六batch完整approval record须独立再次最终签署／确认，reviewed_at晚于binder时间；再重算完整六batch hash、改绑30candidate及确切审核字段。不能仅新增一个未被当前资格判断认可的候选审核旁签来宣称write_ready。

## 全部文件字节SHA-256

下列文件路径均为上述独占目录加文件名。manifest另列在末行。

| 文件 | SHA-256 |
| --- | --- |
| `approved-name-snapshot.fresh-clone.json` | `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570` |
| `bundle.final-review-pending.json` | `7afffbb95a917775d1d3b7e42acc0d2eee1efc41a87d75ccf0bfcc9b1f983023` |
| `clone-stop-receipt.json` | `3ddead71c18baf7bde3414bbc1c834b140499b0d2c34a4d7fbe504f1ee894358` |
| `dry-run.actual.json` | `d607c33337401faed403de1180818f41d25852d38853523f2d255f37b5a89bad` |
| `evidence.anchors.json` | `d986c9ce871cb100679c96bffd5cde1915f387d59dd4ed03a15ab7aa262a2d64` |
| `inventory.fresh-clone.json` | `c5bd21b16ed29ba5657e8664ab30c113550898aa0560e11cdf3e46191b536264` |
| `owners.approved.json` | `fc3bdafda183dc98b493cac2fe9b435f8f383f3abf7fd2734c8d91fe2f26301b` |
| `preimage-capture.readonly.json` | `d6c1aa300c6071d99ef9d5a970f99e52818fd5fb1221c30f0507fe8a1d37baab` |
| `primary-five-candidates.pending.json` | `f154a647f16faaab1870df78ee77ba089c9a4e9be0d08f43095715101bf52288` |
| `producer-record.json` | `efb5f50d48f781ec97a1bf755b8c2d957a37a949efdef28714bb99b4333552c0` |
| `raw-anchors-v3.approved.json` | `f2349f4c9b3c435c9203c25981ad9393627d523bd9e72b38707576143e4fee6c` |
| `registry.json` | `2cfd665b215d1e8651ec9313953504d7c9ac0536d02548bfb8b8f80210593911` |
| `secondary-candidates.batch-approved-final-preimage-pending.json` | `e9b4d1cc1c18876e211f327ff3eb332404a56f84720effa813c57636379928b0` |
| `transliteration-batches.approved.json` | `169320542a662422c10d858726cf33e1b61f3ac0e42fb8e2deef611836aa5b78` |
| `transliteration-section.batches-approved.json` | `6b15c440f25a2eda23f8dd58072cdc51c2e0dd64432d0e086cf85ed69cc847bf` |
| `validation.actual.json` | `2748e3e4f6611e1fe1519c5c3e22786da007277880d1e4ab446165740412f386` |
| `manifest.json` | `eafbcaabe8e96a076523014d94cf567fe7d16507748aa05f0743d0f788136d03` |
