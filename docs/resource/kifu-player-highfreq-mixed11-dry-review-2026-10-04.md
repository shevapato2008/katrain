# 高频混合11人实时capture及事务回滚预演

两库各2,927候选、25hold、11 exact raw、0保护旧FK槽。复用已验证exact importer及models，在独立/tmp/mixed11-import中只允许capture/dry；run_exact_plan(apply=False)，核验inventory和review SHA及current_database。没有apply。

真实事务内锁表、整份前像检查后更新候选FK、验证hold和catalog/name/alias/evidence前像，并ROLLBACK。回滚后再次capture，两库计划SHA完全相同。四个传统重复目录ID均在plan.catalog保护范围。

|库|plan SHA-256|
|---|---|
|TEST|`aaf832ccb09d96ba312ebad5cf27d8431fa602b3332f164814c8cceb93de52d7`|
|PROD|`febd86d8d1c64110ea551ca470e85a38e1aaa2ecd071705bcdf4091a0caea7e3`|

生产临时目录权限导致一次plan文件写入失败（数据库capture读取已经通过），改用同容器root运行相同仅capture/dry runner完成；没有修改业务代码或持久数据库。TEST回传scp失败改用ssh cat二进制取回，并重新核验本地文件SHA。

官方身份与25hold理由见mixed11-review文档。该研究仍需独立审核，尤其鲁佳入段年旁证与吴依铭/蒋其润的间接入段年份；不能把预演成功视作名字或执行批准。

源正文落地：~/.local/share/kifu-name-audit/2026-10-04/mixed11-primary-variant-research/manifest-partial.json。sport.gov.cn本机DNS失败，相关官方内容通过web工具直接读取；partial manifest只记录实际取得的7份HTML，不表示全部来源正文已冻结。
