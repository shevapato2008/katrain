# Ranks101–150：mapping 批准后重产五条 pending anchor

2026-10-03。Producer：`/root/player10_hold_resolution_sol`，模型 `GPT-6 (runtime identity; subtype unverified)`。仅离线来源工作，无 DB、应用代码改动、commit/push；不自审。

独立输入审核 manifest SHA：`3ae5a7e51342754ebf4d21ddd4c3f23fdc00ed2dacd4459b5297efddc3a50fd6`；mapping 实际审批时间为 `2026-10-03T09:16:30.762452+00:00`。新五条锚点实际产生时间 `2026-10-03T09:19:37.439286+00:00`，逐条验证晚于其 mapping 审批时间。

受控包：`~/.local/share/kifu-name-audit/2026-10-03/player-ranks101-150-dependent-anchor5-pending-sol-v1/`，目录0700、文件0400。Manifest SHA：`24c4625607bd47fc396d62006ea76b7d012c19f65855a00f62f53d36540250d5`。

`anchors5.mapping-bound.pending.jsonl` 精确包含金明训、伊田笃史、罗玄、Hane Yasumasa、杨子萱。每条嵌入完整已批准 exact mapping；`change-bindings5.actual.jsonl` 给出其 canonical SHA、旧/新 anchor SHA 和时间关系。金明训、罗玄的 normalization basis 同时绑定完整已批准有限韩国别名记录 SHA。原始 source 数组、名字、读音和有限 scope 均未改变；其余三个 owner 没有添加别名规则。两个已签依赖文件原字节复制，未扩大审批。

实际检查了输入审核全部 manifest 文件 SHA、五条 owner 精确集合、mapping 的 approved 状态、逐条时间顺序和 source 数组不变。**新 anchor 5 pending / 0 approved**，剩余闸门仅为这五条新锚点的独立复审；既有20 PASS和本轮已获批另5条锚点不由本包改动。候选译名、通用规则、批次、导入与部署仍不在本包审批范围内。
