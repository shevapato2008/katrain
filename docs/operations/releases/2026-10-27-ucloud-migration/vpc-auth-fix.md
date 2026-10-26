# VPC 迁移临时 SSH 授权修复

完成时间：2026-10-27 上海时间约 01:16（UTC 2026-10-26 17:16）。旧机临时授权写权限已释放，controller 可接手传输及最终清理。

## 结果

新机 root 已使用现有临时 transfer_key，通过 VPC `10.60.162.188 → 10.60.219.118` 成功登录旧机 ubuntu，并成功执行 `sudo -n`。

实际验证命令启用 `IdentitiesOnly=yes`、`BatchMode=yes`、`StrictHostKeyChecking=yes`，使用现有 `transfer_known_hosts`。退出码为 0，输出：

```text
10-60-219-118
ubuntu
0
backup-readable
```

分别证明旧机 hostname、登录用户、免交互 sudo root UID、原 authorized_keys 备份可读。

## 原因与唯一修复

旧机运行 `OpenSSH_8.9p1 Ubuntu-3ubuntu0.10`。该版本本机 `/usr/share/man/man8/sshd.8.gz` 对 `expiry-time` 的说明只接受 `YYYYMMDD` 或 `YYYYMMDDHHMM[SS]`，按系统时区解析；不接受此次使用的末尾 `Z` 语法。旧机系统时区为 `Asia/Shanghai`。

只修改 `/home/ubuntu/.ssh/authorized_keys` 最后一条迁移授权的到期时间语法：

```text
expiry-time="20261027010738Z"
→ expiry-time="20261027090738"
```

两者表达的同一绝对到期时刻为 **UTC 2026-10-27 01:07:38 / 上海时间 2026-10-27 09:07:38**，没有延长有效期。

保留：`from="10.60.162.188"`、`restrict`、公钥指纹 `SHA256:Gg2r1puj7RGqua5UIZh6eLtCoqDBUOPaMOdNgIyjuNA`、原有三条授权，以及原备份 `/var/lib/ucloud-migration-20261027/ubuntu-authorized_keys.before-transfer`。文件仍为 ubuntu 所有、0600；目录和 home 权限本来正确，没有修改。

## 范围与证据

未修改 sshd 配置、端口、host key 检查、用户密码、服务、writer、DB 或 DNS；未复制 Mac 私钥、未使用 agent forwarding。

私有结构化日志（目录 0700、文件 0600）：

- `/private/tmp/katrain-migration-501/private/auth-debug/expiry-syntax-fix.json`
- `/private/tmp/katrain-migration-501/private/auth-debug/vpc-key-sudo-verification.json`

授权文件修改前 SHA256：`a73c7acc48ca258c90a9484827a1c8cb4521f932e87385b084203fdbdf5aaae3`

授权文件修改后 SHA256：`7f9578a6b90a1df67d8af6c1a9533d75f55a691a44752cd7512bcf20935d32cd`

传输结束后由 controller 清理这条临时授权及临时私钥；本修复任务不再持有授权行写权限。
