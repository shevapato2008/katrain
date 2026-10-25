# Kiosk 等级身份与来源追查

本轮只修改两页共用列表展示：同记录明确9p→职业九段、6d→业余6段、6k→6级；繁体使用職業／業餘，非中文保留既有formatter。没有明确p/d身份的裸九段保持原文；只有同记录typed raw且段数相同才补身份，不根据姓名、职业库类别或当前profile推断。

原未知值“—”在18px楷体中容易被看作中文“一”，现在显示“未记录”，保留完整辅助说明。字号及镜像位置不变，长名仍保留开头、完整title。[代表前后](screenshots/comparison-reports.png)左前右后、同输入、1024×600楷体大字号；[Astra独立预览](screenshots/astra-after-reports.png)。均是匿名固定输入，不能当成最新三盘已有真实9p的证明。

## 源链结论及此前归因更正

此前只读本系统preview SGF无BR/WR，只能证明系统保存/读取结果为空，不能因此断言源站没提供。这一过度归因现明确撤回。随后独立原同步负责人只读核对三条真正19x19源响应、stage/canonical/冻结包/TEST/PROD与当前官方实际消费者，并由fresh Astra复核。

[过滤后的证据表](rank-source-evidence.json)，SHA726905b28fac37d889b15611fe53fd6c58ebceab2ea72b65f823e2829be6714d；[完整有限调查说明](source-investigation.md)。

- 三条source IDs91694911/91638738/91637528，对应TEST179093/179085/179084、PROD178757/178749/178748。原shared HTTP200只有id/userCode/sgf，PB/PW纯姓名，BR/WR缺失；原SGF→stage→canonical→冻结包→PROD逐字节hash相同。
- 列表metadata两侧3002在stage及冻结source_metadata完整保留，未被姓名模型/serializer删除。现有derive_metadata只消费明确BR/WR、black_rank/br、white_rank/wr；不能直接将3002塞入rank或映为9p。
- 官方91694911当前真实239手页面把3002传给UserInfo/levelCom，但levelInfo/levelName/DOM均空。实际GLOBAL.getLevel(3002及字符串)返回value0/空label/name；最终53项及动态39项字典均无3002。旧注释表不能当当前九段或职业9p合同。
- 官方当前保存模板BR/WR也为空；未成功得到新的官方导出文件（匿名点击10秒无事件，helper报null.value），不声称已成功下载、全站绝无其他接口或3002已证实为统一占位。实证范围限定三条源链及91694911当前消费者。
- 当前profile的professional/proName/proLevel属于当前资料，不是历史当局段位。本轮没有访问profile或用姓名补身份。

因此当前证据不足以给这三盘补真实职业段位；保留原SGF、raw level与所有冻结/数据库记录，缺值如实显示未记录。若以后取得可信当局证据，再按有限sourceID+SGF SHA+旧rank幂等更正。本轮没有中央数据回填、重采、重译或冻结包修改，也不宣称全库段位补齐。

## 审核及验证

fresh独立gpt-6-astra/max已批准固定产品候选0a6399cf163c05f225b6205d5b034b124c57daa3的有限方案：显示修复＋本轮调查结论，无must-fix。它独立核对源证据SHA、官方脚本SHA、8处消费者片段、运行时字典与组件值；UI11/11 helper测试及真实1024×600预览通过，职业九段/业余6段/6级/未记录均18px，无长名碰撞或页面溢出。负责人71项聚焦及TypeScript通过。批准不等于这三盘或全库历史段位已补齐。

已按授权完成feature追最新develop、推feature/develop、Smartbox gitlink与main推送及RK定向发布。


## 发布回执

| 项目 | 已核实版本 |
| --- | --- |
| published develop / feature | 2e7640d892e311f3fc8ed70d4dc5a32e470d2ddf |
| Smartbox origin/main | 350c927bade41104670fbe4b414a8ceb60e5bb62 |
| vendor/katrain gitlink | 同上述published develop |
| RK实际进程KATRAIN_BUILD_SHA | 同上述published develop，PID591004 |
| 实际严格入口 | index-DRVGXi41.js |

[设备校验](verification.json)、[原页与身份恢复、真实卡片文字](browser-verification.json)、[文件清单](manifest.json)。原fan身份200、原/kiosk/kifu及1024×600保持；三条实际卡片的未知段位均明确显示未记录、18px，结果相对姓名中心差0px。相应列表原rank仍为null：这验证显示修复，**不代表三盘真实历史段位已补齐**。

391受控Python、19路policy及同源full/strict共1189文件哈希通过；462项配置/身份/模型/标定/字体保护状态不变。只有围棋服务重启，Kiosk及围棋target未动，原19路功能验证保持。没有中央棋谱数据回填、profile查询、新采集、翻译、冻结包变更、付费报告或实体盘操作。SSO通过真实主页→围棋恢复，不读取/注入cookie。

回滚材料保留于 /mnt/data/smartbox-deployments/20261025-kiosk-rank-identity-2e7640d89/，含[rollback.sh](rollback.sh)、旧受控源码/静态/标记与在线SQLite快照；未执行回滚。本次上传包/解包候选已清理，源站调查和原始采集缓存未动。现场截图仅留本机/tmp/kiosk-rank-identity-release-20261025/receipt/browser-after-restored.png和设备同发布目录。

本回执提交仅文档，在独立evidence分支保存；实际部署源码保持上表published develop。
