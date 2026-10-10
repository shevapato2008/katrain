# 职业棋谱默认规则发布 — 2026-10-07

## 策略

用户明确授权：没有规则时安排默认规则进行分析，贴6.5目默认日本规则。实施映射为显式KM6.5→Japanese，KM7.5→Chinese；其他/缺失KM保持待核验。合法原谱RU及已核验赛事证据优先，保留原始SGF，不修改贴目。

默认分析快照为version3、verified=false、provenance.source=komi_default、policy=komi-default-v1。参数身份和逐局面hash仍严格匹配；v1/v2核验快照及hash保持原样。API parameters_valid区分可用性，parameters_verified区分实际规则核验。列表可展示默认分析的报告，Galaxy/kiosk注明“日本规则（默认）”，详情说明按贴目默认、未核验赛事实际规则。未绑定参数的旧结果不能直接改标签发布。

## 代码与部署

规则实现提交b6219096；本记录同提交另外修复Galaxy紧凑规则行的截断：赛事结果可省略号，规则与贴目完整保留。Python参数/API/worker/transfer回归102项、前端聚焦34项、typecheck、standard/kiosk2D构建通过。独立gpt-6-astra max对方案、代码、局部部署及同步覆盖事务审核通过；同步先锁定并复核完整备份状态后才删除旧行。只覆盖resolver及analysis endpoint函数，保留并行发布的标题/搜索/模型代码和compose配置。

home镜像web/cron为`katrain-{web,cron}:default-rules-home-20261007`；prod对应`default-rules-prod-20261007`。standard index SHA256 `df74af1faccd80e83ffac705fd05e809fa3aa41d495745d43f459f01aeb59686`；kiosk2D index `904dea02ff35825f783efc668c98cd56356a640496807c36b223a4a2fcd9d39b`。资产先复制、index原子替换，保留旧hash资产。个人/直播行为与在线GPU未变；主cron职业批量开关仍false。

## 重算批次

9局：24160、24161、24164、24165、24166、24167、24168、24169、24171，共1,732个局面。两库原谱及快照预检一致，冻结manifest SHA256 `7ee91b16ab983162d0b4e6834e509a84e3a52333b7add9e22b0588e8c3d1c5cd`。全部原谱缺RU，KM6.5，使用日本规则默认。home-ubuntu两个隔离SQLite工作库：GPU0四局809局面，GPU1五局923局面；模型s11003M-d5973M-7gres，2000 visits。正式机没有批量引擎任务。

历史151913（缺KM）及168220（KM0）仍未选择默认，不在本次批次。

## 完成结果

- 9/9局、1,732/1,732个局面计算完成，两个隔离工作进程退出0；2026-10-07 15:04:59–15:33:33（北京时间），整批墙时约28分35秒。
- GPU0四局平均428.68秒（7.14分钟），GPU1五局平均325.25秒（5.42分钟）；本批所有棋局平均371.21秒（6.19分钟），范围233.96–564.06秒。单局手数不同，此均值不代表统一长度的比赛耗时。
- 先验证全部完整结果，再备份9份旧报告、锁定并复核旧状态、重置、dry run及事务导入。home备份SHA256 `50fa456c90426ccadab25bfa50e54dd075f9eb5be832722d42e0e9143ffa69d9`；prod备份SHA256 `8cb4f0b3b3c624bc0d4cfb0a6e55e9e38cab48069d1079bd9ef525fbdf381620`。备份在两机本轮任务目录的`backups`，权限600。
- 测试库与正式库完整9局报告导出SHA256同为 `bd0432be4353f70f97a46d42033f781e5c9a774e758edce780bab842ba5bab74`；两库逐一确认原始SGF未变化、参数完全匹配、局面行连续，最小实际root visits=2002（请求2000）。
- 两库这9局候选/ownership JSON字段实存共5,198,006字节；不包含行、索引及其他字段，不当作整库空间成本。
- 公网两站API再次逐一验证9局：completed、parameters_valid=true、parameters_verified=false、日本规则6.5、v3默认来源，全部逐手结果和参数SHA一致。第一页20条最新24171及本批对应条目has_analysis=true；原已核验24163仍verified=true、210个局面可读。
- 两站实际点击棋谱库的“查看分析报告”，均进入`/galaxy/kifu/24171/report`；点击后的实际页面快照确认默认规则、贴目、候选和走势已显示。第一次一体化自动检查超时，随后以请求事件和页面快照分步确认，未因此修改业务代码。
- 已亲自目视检查两站真实24171：Galaxy1440×900、kiosk1024×600、规则详情，报告数据可见。Galaxy默认标签与分析贴目完整显示；详情字体一致，明确SGF未记录规则、按6.5默认日本规则、未核验实际赛事规则；kiosk无3D按钮。截图在`output/playwright/{home,prod}-default-24171-{galaxy-1440,kiosk-1024,galaxy-details,kiosk-details}.png`。
- Galaxy标签修复后的7项MetaPanel回归、typecheck、standard/kiosk2D构建通过；2D边界无three.js。独立gpt-6-astra max已对最终两站Galaxy截图及该CSS修复给出APPROVED。
- 自建GPU0批量引擎`katago-verified-kifu-gpu0-20261007`已停止。现有在线引擎保留，正式机无本次批量计算。
- 同步helper初次启动缺PYTHONPATH导致import失败，没有写数据库；修正为`PYTHONPATH=/app`后执行完整同步成功。二次静态发布prod因stage目录root权限拒绝，改为已有sudo -n权限后成功；该失败发生于提取前，未替换线上index。

## 实际入口

- [测试桌面报告](https://go.sailorvoyage.top/galaxy/kifu/24171/report)
- [正式桌面报告](https://modelstella.com/galaxy/kifu/24171/report)
- [测试盒端报告](https://go.sailorvoyage.top/kiosk/kifu/24171)
- [正式盒端报告](https://modelstella.com/kiosk/kifu/24171)

