# 四赛事有限关联：实际入库

2026-10-05，TEST和PROD均顺序完成真实dry回滚、apply、完整前后像verify。共1,117局：日本龙星424、台湾棋王328、日本女子名人253、韩国名人112。48个冲突/范围不明候选不写，旧4,768 Hold、隐藏250、duplicate和已有赛事/届次FK均排除。

主线程独立阅读固定scope、原始SGF根属性、官方留存证据及type123执行器适配；每份实际planSHA独立批准。仅更新event_id，完整album/source/event/names/evidence前后像核对，其余届次、轮次、raw、SGF、赛果与棋手FK保持原值。两库各4类×5语言的真实详情API共40项均通过。

最终正式库：五语棋手162/3,700（4.3784%），五语赛事类型64/85（75.2941%）；五语赛事覆盖105,977/173,025局（61.2495%），双方棋手＋赛事五语完整覆盖24,458/173,025局（14.1355%）。详情和每类提交后的真实统计保存于`kifu-incremental-applied-2026-10-05/event-fk-{40,53,34,49}-{TEST,PROD}.json.gz`，包括scope、完整plan、独立批准、执行器、官方原文及dry/apply/verify回执。

名称工作继续进行。关联完成后由另一agent只读捕获一次新format4库存，恰1,117个event_id变化，逆置恢复旧base SHA；source/player槽/selection不变，定向SGF SHA一致。后续pending名称只重绑inventory摘要再验证和独立批准，现有快照漂移闸门不放宽。
