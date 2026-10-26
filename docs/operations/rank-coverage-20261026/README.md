# 2026-10-26 公开棋谱等级覆盖缺口

这是新缺口的调查与后续修复记录，不复用前次三盘批准作为本轮全部通过。

用户截图来自 Galaxy `/galaxy/kifu`。中央 API 与 RK 当前第一页的40个位置一致，已补六侧证明旧UI有效，无需改字号/CSS或重启RK。当前用户设备只作已登录公开页fetch，没有导航/切模式。

| 棋手 | 当前 PROD / source | 唯一实体 | 库内最新明确原值 | 既有官方主体 |
| --- | --- | --- | --- | --- |
| 於之莹（display於之莹） | 178745 / 91635363 | 218 | 2026-10-03 八段，90638040 | baduk pkey20000560，原文於之瑩 |
| 芮乃伟（display芮迺伟） | 178744 / 91634842 | 209 | 2026-10-15 九段，91284543 | mobile PRPL_CODE10000186，原文芮乃偉 |
| 党毅飞 | 178743 / 91632021 黑 | 127 | 2026-10-09 九段，90903437 | baduk pkey20000536，原文黨毅飛 |
| 辜梓豪 | 同盘白 | 37 | 2026-07-19 九段，85428764 | mobile PRPL_CODE20000629 |

当前三盘 raw 两侧均为空，没有snapshot；原SGF SHA/明确source/FK等详见 [四位及同盘对手](prod-four.json)。等级依据来自库内绑定原谱，职业主体来自同owner已有独立审核的官方捕获，不根据名气猜九段。

原导入 run72633（UTC10-24 08:54:49→09:37:37）发布党/辜，run72739（09:54:49→10:31:56）发布於/芮，两者success/error_count=0。原native包为v1，无rank阶段，三条StateStore已prod_synced、last_error=null。这不是当时rank exception；93f以后已发布/已packaged会跳过prepare，且此前有限纠正只含三个别的sourceID，故这几盘没有重新补值。现场重新只读lookup才返回professional_identity_unverified。[原run/StateStore](original-run-and-state.json)、[原native和run](original-native-members.json)。

另有真实新源91737274（小池芳弘–萧钰洋，10-26，PROD178758）已经正常插入，但两侧冻结unknown。UTC06:16:22的rank INFO是unknown=2/unknown_system=2，没有exception；当轮run77467最终success。原日志只有聚合，没有丢失职业资格的具体reason或source/side关联；这是可观测性缺口，不伪称服务崩溃。[有限原日志](recent-rank-log.filtered.json)。

本次调查时第一页20盘40侧：raw明确等级0；snapshot8（六侧旧fallback、两侧新谱unknown）；显示fallback6、空34。现场lookup：33侧professional_identity_unverified，1侧李小溪94 no_verifiable_raw_rank。该数字是固定有限页面，不等于整个七天或全库。详见 [有界清单](page-before.json)。

修复范围：将既有官方profile/roster消费者从六人白名单改为支持schema内的exact主体/唯一记录；同条已审核approved alias可exact命中，不做简繁/括号/姓名猜测。旧六proof/fact摘要必须不变。新日志只加固定reason统计和至多200个公开source/side。显式correction scope至多20 sourceIDs，逐条pin原SGF/原manifest，冻结/CAS/原生同包TEST→PROD验证和重放，原谱/原rank/原包/ID/状态保持；未可靠命中继续列明为空，不动态用current覆盖历史。

本目录当前仍是调查/开发证据；真实后续部署、有限纠正、独立审核与最终覆盖结果须补后续记录，不能把以上候选值当已上线。
