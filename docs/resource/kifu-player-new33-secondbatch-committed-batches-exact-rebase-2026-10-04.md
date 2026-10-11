# new33 第二批：已提交批次精确重基线

JSON SHA-256：`70d57853166704203003935186c68de1e78e6f2382db8a1e29d2c1df1af06509`。基础身份决定 SHA-256：`dde6d06c6ada0b1520a9854a212a8a28de3e72809abffe2ccc2945e44bb795fb`。

2,755 个批准槽、543 个本批 HOLD、4,075 个排除边界成员完全不变。

独立重放 next3 → 首批棋手 → next514：两库八个新捕获完整后像与推导值完全一致，额外字段差异为 0。37040/75303 仅对手 white_player_id 改变；73249/75293/106142 仅 event_id 改为 75。7 个新棋手行、2 个新赛事行及既有赛事 75 的创建时间与完整内容已固定。

保留所有前置 HOLD。next514 另与全 new33 边界的旧 HOLD 35821、66361、139660 相交，已列入 full8 actual capture，并按执行计划/回执独立重放验证完整后像。首批所有 1,439 行、1,451 个 FK 变化也已精确重放，以便完整守卫当前边界。

补充含每个剩余 3,298 槽在两库的有效完整行 SHA、对手目录 SHA、SGF/来源守卫，以及全目录和范围摘要。可继续构造新的精确环境计划与回滚演练；执行时必须核对完整 current 前像，任何额外漂移均失败。没有 DB 写入或代码修改。

| 证据 | SHA-256 |
|---|---|
| 首批执行回执 | `1ed3152265353df24884cb1d87140f2eef99b9a6e295d1b117b8d85b50b83e05` |
| next514 执行回执 | `0328d5bec347b97cfa18a6930646d512b2da935e8d0d2f540ce0b5f13fd5c6c4` |
| TEST firstbatch_applied_plan | `2534207b89dc911a7378f4279a664ce7036d873946ad73b659369f4cbc1261b1` |
| TEST next514_applied_plan | `ce2ccba64c0780694a64da5a4724a1f195bd219639462119f5eaf239e23af2db` |
| TEST actual_cross_batch_postimage | `5002519406873f2c33cf70003a6d4ac7ebb7146c4d879c5e31f527e146267f39` |
| PROD firstbatch_applied_plan | `eb4c443969a8f998037de9ac241e14562e53bae109fec67ec5a0cdbc835cbe79` |
| PROD next514_applied_plan | `8ec2afbe6c0ab5fa7e4524311e9602bc6e955021b65bcdcb129c71827babade1` |
| PROD actual_cross_batch_postimage | `8944b9f2194abfccda72302cae1ed75ae43d6025ba49e30b9a7f71c2ca919a70` |
