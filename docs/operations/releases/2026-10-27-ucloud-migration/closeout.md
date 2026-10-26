# 控制者收尾补记

本页补记独立审核完成后的新实证，不修改审核者原文，也不冒称这些是审核者独立复查的结论。时间均为UTC，括号注明北京时间。

## 自然小时轮

恢复原调度后自然运行79033：2026-10-26 22:17:20.604512→22:20:17.281807（10月27日06:17:20→06:20:17），176677ms，success、error_count=0。没有手动触发采集、改变预算或额外模型调用。

当前head与coverage均属于这轮：比赛窗口为北京时间10月20日06:17:24至27日06:17:24，head5页、每页20、100个唯一源项；比赛日期超窗55，未知时间0。HTTP46、SGF检查41，terminal_count19，未用尽SGF/请求/时长预算，recheck0。head_page_cap=true、boundary_in_window=false如实可见；这不是全源覆盖保证，更没有推进历史rolling。现有源站缺可靠updated_at、近7天/硬14天比赛窗及3300秒协作预算等原限制未改变。

该轮journal batch/item更新均0，未产生新TEST→PROD包；模型审计在该轮时间窗内0call/0reported tokens。UTC当天累计13116/100000 tokens、12call、0 unsettled属于累计，不能归为这轮新增花费。同一冻结包链路由另一次真实原生幂等重放证明，不混淆这两个证据。

原始私有证据：`test-endpoint/natural-hourly-run79033-result-20261027.private.json`，SHA256 `e278223930ce02a571dcf0543b1891cfc978344a08750cdeea534d480d23365e`。

## 离机备份

最终13库归档已离机到Mac：2473472000 bytes，SHA256 `fc53fba5b1080a93a534cbabc1e530438aef335533674e27e60161c0833a6740`。完整流SHA与原子rename通过，随后本地重新读取tar，13库/4globals/16配置共33个payload逐尺寸/SHA校验通过。内嵌原manifest SHA256 `3b8d2b9da4ebab869c8a0b5745aa749eda95fa428d09a478f3cef78e983a8a9e`。

最终非PG归档于UTC22:44完成Mac原子rename：3872061440 bytes，下载流核验通过后控制者再次独立完整读取本地归档，SHA256 `6ac730c0af7ea125b3db2d13e333d854af726b1bf40ed659973ef3a52a4defd3`匹配；.partial不存在。与新机冷归档一致，目录700/文件600。旧机继续保留。

## 实际运行及权限清理

UTC22:41新机实测17容器全部运行，配置healthcheck的全部healthy；主health200、根盘可用35GiB。此前临时迁移SSH授权已精确撤销，旧authorized_keys的其它原字节保留，新机临时私钥与.pub已删除。常规Mac管理身份经新机内网代理访问旧机仍严格校验hostkey并sudo成功，未复制用户私钥或关闭校验。

TEST8个及新PROD7个控制已按原前像全部恢复absent，真实标准writer锁均已释放，当前无遗留维护暂停。旧机写端保持围栏，新机是后续新写入权威。

## DNS待接管动作

阿里云云解析`modelstella.com`现有5个A记录：`@`、`www`、`lobby`、`ranked`、`pitch-api-staging`，当前值均117.50.183.169/TTL600；目标仅改记录值为117.50.177.254，保留类型、TTL及其它记录。既有OSS身份调用AliDNS返回403 Forbidden.RAM，当前没有有效zone编辑凭据或经验证的控制台会话。没有扩权、购费、更换凭据或读取密码文档。

取得已授权的DNS编辑能力后：先核现有记录并留前像，修改上述五A，直查dns27/dns28.hichina.com及实际resolver；至少等待旧TTL与旧连接排空，重复新公网TLS/五域health、Galaxy/媒体Range/WS代表验证，确认不再依赖旧proxy。随后验证现有ACME webroot/nginx challenge可路由，恢复新机certbot续期，删除新nginx仅信旧private10.60.219.118的临时real_ip配置并nginx -t/reload。旧机不恢复writer/VPN/certbot。

**can_retire_old=false。** 删除旧机目前会切断五域入口。只有DNS/排空/TLS续期/旧private信任撤除/最终离机备份及无其它旧端依赖全部确认，才可重新判断退旧；实际删除仍由用户另行操作。新机已有新写入，不能直接复活旧库作为无损回滚。
