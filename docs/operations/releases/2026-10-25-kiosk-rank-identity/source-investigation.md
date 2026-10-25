# 星阵段位来源只读闭环（2026-10-25）

结论：当前官方线上也不能把三盘源元信息中的3002显示成具体等级，更没有可靠职业p／业余d身份。不能把3002直接加入rank别名、转为9p或按姓名补段位。此结论来自真实运行时与同一盘实际页面，不依赖被注释的旧映射。

## 当前官方实际消费者

实际打开官方分享URL `https://m.19x19.com/app/dark/zh/sgf/91694911`，自动进入 `https://www.19x19.com/engine/analyse`；239手已加载，赛事及藤泽里菜／上野梨纱匹配。

1. 官方列表的 `gameInfo(e)` 把blackLevel/whiteLevel装入br/wr，但实际研究页 `sgfInfoCom.blackLevelString/whiteLevelString` 从gameMeta.pbLevel/pwLevel或blackLevel/whiteLevel取得3002。
2. 实际render把上述值传给UserInfo.level，再传levelCom.level。两边实际level=3002，levelCom.levelInfo=''、levelName=''、DOM文字=''；UserInfo DOM仅有姓名。
3. 当前GLOBAL.computerLevel为53项，没有value=3002；GLOBAL.getLevel(3002)和getLevel('3002')均返回 `{value:0,label:'',name:''}`。getLevelListNew()同样没有eloScore=3002。
4. 动态初始化为pageStart→updateAiLevel→loadAiLevel→GET `/api/engine/ai/name/list?group_name=golaxy`；该真实HTTP200/code0响应为39项，没有3002。updateAiLevel合并初始表，实际最终53项仍无3002。3000的AI9段是另一值，不能用于3002。
5. 当前该盘gameMeta只有blackLevel/whiteLevel两项等级字段，没有pbLevel/pwLevel或pro rank字段。原始shared JSON仍仅id/userCode/sgf。

## 导出消费者与实证边界

实际保存到本地面板，BR/WR均null，PB/PW是纯姓名。显示链的metadata 3002与导出sgfInfoTemplate的空BR/WR是两份状态。当前app链：downloadSgfConfirm→board.downloadSgf→CreateSgfData→SgfParse.CreateSgfDataByStep→sgfHeadCreate→sgfHeadHandlerInfo。最终header writer只把非空value写成PROP[value]，不做等级或职业身份转换。

匿名会话的实际保存点击未产生download事件（10秒即止）；直接只读调用已加载app的createSgfByBoard导出helper也遇到null.value异常。没有声称成功得到新的官方导出文件，也没有扩展排查官方工具链。真实页面的可见结果、组件实际计算值、运行时字典和导出模板已足以证明此样本当前不提供可消费的具体当局段位。该会话观察到的棋谱请求只有`/games/meta/null/91694911`与`/games/shared/91694911`，没有观察到补充真实BR/WR的另一个export API；不能据此证明全站不存在其他接口。

## 三盘各层证据

详见rank-source-evidence.json的samples：包含source ID→TEST/PROD id、比赛日期、原HTTP状态/JSON键/响应SHA、SGF SHA、stage raw及metadata路径、冻结包/manifest SHA/publication key、原生双库receipt、API空rank。源→stage→canonical→冻结包→PROD SGF逐字节相同；BR/WR和姓名内嵌段位从源原文即不存在。metadata两侧3002在stage与冻结source_metadata仍保留，未被模型或serializer删除。

## 最小修复建议

现有明确9p/6d/6k可做正确身份格式；这三盘诚实显示未知，保留上游原始level。当前缺少可解码的具体等级和职业／业余身份两个证据，不能用旧注释表补齐。若另行采用官方棋手当前profile段位，应显式标为当前资料、绑定可信身份及查询时间，不能静默替换历史当局段位。若未来取得可信当局rank，再按有限sourceID+SGF SHA+原rank做幂等、可审计纠正，保留原SGF/冻结包/回执，不重导或重译。当前无需也不应从3002自动回填。

## 精简复核文件

- rank-source-evidence.json：完整过滤后字段表与运行时结果。
- runtime-evidence.json：真实页面GLOBAL与组件值、具体函数、可见文本、相关资源路径。
- runtime-meta-fields.json：实际官方该盘元信息字段列表及等级字段。
- ai-name-list.json：唯一新增配置GET原始公开响应。
- consumer-source-excerpts.json：已校验SHA的当前app关键代码片段与字符偏移。
- .playwright-cli/page-2026-10-25T11-16-50-594Z.png：官方实际页面截图；两边姓名均无段位。

所有业务环境操作均只读；只写入本机临时调查目录。没有修改repo、数据、服务、scheduler、锁或prod_synced，没有触发采集job、导入、翻译或发布。
