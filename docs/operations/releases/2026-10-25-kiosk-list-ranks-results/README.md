# Kiosk 列表历史段位与结果展示

仅覆盖职业棋谱库列表与个人复盘历史卡片。两页共用纯展示名单行：[黑子][左姓名][辅助段位] | [结果] | [辅助段位][右姓名][白子]。没有修改 Galaxy、对局/观战名片、报告任务、数据库或原 SGF。

## 数据与结果语义

职业列表使用本条记录的 display 段位，空缺时回退同条 raw 段位；个人历史只用当局保存的 black_rank/white_rank。沿用已有规范，9p/9d/6k分别显示职业9段/9段/6级。真实未写的等级以“—”和“等级未记录”辅助说明表示，绝不贴当前账号等级或按人名猜九段。

已有中央分页合同具备所需字段，无新增云端合同发布依赖。只读原RK认证页有限抽样：两个API200，个人历史authority=cloud，其中当局白方6k；职业最新3条原始/展示段位都空，列表自带首条preview的系统保存SGF经现有SGF parser确认BR/WR也为空。这份初步检查不是源站证据；此前将它归因为源站没有段位的说法撤回。真正源链与当前官方消费者核验见[后续调查](../2026-10-25-kiosk-rank-identity/README.md)。记录见[source audit](source-audit.json)，未保存私有SGF/棋局ID，也没有全库扫描、批量历史写入或逐卡SGF请求。

结果仅在这两个Kiosk列表使用窄范围helper，明确的W+R→白中盘胜、B+Resign→黑中盘胜，白认输表示黑中盘胜并只高亮黑方。数字继续原规则单位，例如B+6.5→黑胜6.5子，不再泛化搬成黑6.5子胜。T/F继续超时/弃权；Draw、Void、空结果和未知不当成中盘。历史空结果按原来源保留“未终局/没写结果”，Void保留未判胜负语义。其他语言及通用formatter未修改。

## 真实视觉核对

[职业前后](screenshots/comparison-kifu.png)、[历史前后](screenshots/comparison-reports.png)均左前右后，真实React1024×600、匿名浏览器fixture、楷体大字号。[职业叠加](screenshots/overlay-kifu.png)、[历史叠加](screenshots/overlay-reports.png)、[小字号历史](screenshots/after-small-reports.png)、[原Kifu结果参考](screenshots/reference-old-kifu-result.png)。

结果复用原Kifu的1px #53645a边框、5px圆角、透明底、18px辅助层级，并在共同grid中相对姓名行居中。旧DOM结果容器本已接近对齐，未虚报原有大几何偏移；差异主要是两套结果表面/行高层级及直接文本裁切。改后容器中心差约0.004px、实际文字Range中心差最大0.406px。卡片高度保留职业78px/历史74px；姓名大字号22/20、小字号18/16，已知和未知段位均18→14px。长姓名从开头省略并保留完整辅助名称，等级有独立宽度上限，不挤没姓名；无页面溢出、结果与姓名重叠。

## 验证及审核

Writing Plans计划经独立Astra Max两轮R2 Approved；subagent-driven-development分两项闭环，[最后代码与视觉审核Approved](../../../superpowers/reviews/2026-10-25-kiosk-list-ranks-results-code-astra-final.md)，无剩余must-fix；唯一非中文历史文案回归已最小修正。76项定向检查与TypeScript通过，full/strict生产构建及SSO/Kiosk边界通过。基线Kifu localization少getAlbum/load mock导致4项既有失败，已最小补mock继续覆盖本切片，并更新本次直接改变的中盘/数目语序断言，未宣称全仓库测试通过。

真实浏览器验证选中另一张卡、分页实际GET page2，删除确认只打开并取消，没有真实删除或报告生成。Fixture只在测试浏览器路由，生产代码没有模拟业务数据。各项测量及交互记录同目录；开发预览在list-match-cards worktree的output/playwright/list-match-cards-20261025保留复现脚本。

发布将按用户已授权顺序完成feature追最新develop、推feature、合入/push develop、Smartbox仅更新gitlink并push main，再定向RK。设备实际版本与回执在发布后记录，避免将本机预览或未发布分支误报为已上线。
