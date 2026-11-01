# Membership local service journeys — 2026-11-02

Task 9.4 的跨模块真实后端整合证据位于 `tests/web_ui/test_membership_journeys.py`。
本轮结果：**4 passed, 16 warnings in 3.78s**。三个业务旅程中，第二个分别覆盖 term / week 不足。

## 实际边界

- 使用专用 loopback PostgreSQL `membership_validation_20261102`，每个用例独立随机 schema，复用 `membership_pg_engine` 清理；未使用默认开发库或生产库。
- 在创建测试主体及安装依赖之前，实际执行 `validate_runtime_environment`：读取 `current_database()`，核对显式数据库身份及独立只读 TEST marker。测试不创建或修改该 marker。
- 挂载完整 `api_router`，通过 HTTP ASGITransport 请求实际业务 API；使用真实 JWT Bearer、`SQLAlchemyUserRepository`、真实管理员角色校验与签名 TEST 支付事件，不覆盖认证依赖或 mock 业务路由。
- Web `get_db`、report session factory、cron SessionLocal 指向同一随机 schema；`autoflush=False`，`expire_on_commit=True`。运行器在加载模块前显式使用内存 SQLite 作为未使用的默认全局配置，未启动应用 lifespan。
- 仅 KataGo HTTP transport 使用 MockTransport。请求仍穿过真实 `KataGoClient.analyze`、请求序列化和严格结果校验；报告使用真实 `ReportAnalyzerJob._claim_pending_task(with_fence=True)` 及 `_process_task`，携带匹配的 generation / operation binding。
- 本轮未修改产品代码、既有测试、生产配置或数据，未调用真实 GPU。

## 已通过的旅程

1. **购买 Pro → 局面 → 复盘**：HTTP 创建 9900 分订单，真实管理员 Bearer + HMAC 事件支付，本人读取 paid receipt；usage 返回 Pro term `27090` / week `9030`。两个独立同账号 HTTP 客户端返回同一 usage（忽略 `server_now`）。普通局面 quote/confirm 同时得到 ownership 和候选着，仅消耗 1 unit、调用一次引擎；同 key 重试、owned quote、另一个 key 的提示/领地显示复用结果，无额外引擎调用。随后从真实个人棋谱 API 导入 N=2 的 SGF（客户端 move_count=0），report quote 为 3 units。pending moves 不可读；worker 生成 0/1/2 严格结果，HTTP 成功结算后可读并发布到个人棋谱分析。最终 term/week 各 used=4、reserved=0，原钱包 137 credits 未变化。
2. **故障全退 → 单来源钱包回退**：会员局面引擎 503 后恢复原 term/week、钱包不变。服务端签发会员 quote 后，分别让 term 或 week 用尽，再以原签名 quote 确认；整笔转钱包，失败先全退，成功后仅扣整数 1 credit（137→136），term/week 不追加扣费。钱包操作不绑定会员 term/week；所有金额/额度取自服务器，不由 confirm 请求发送金额。
3. **受控 TEST 免费报告**：默认资格依赖返回 False，普通未验证账号 usage 为 `verification_required`，免费报告 quote 返回 403。仅在实际 TEST DB guard 通过后，为特定测试主体覆盖资格依赖；该主体一周可获得一次普通报告，不获得局面 credits（零钱包局面 quote 402）。真实 worker 生成成功并结算后删除棋谱，committed receipt 仍保留、资格仍为 weekly_report_used；第二次不同棋谱 quote 返回 402。无会员 term，无钱包赠送。

## 复现

从现有受保护本地 PG 环境文件导出 `TEST_DATABASE_URL` 后运行（不要打印或提交该文件）：

```sh
KATRAIN_DATABASE_URL=sqlite:///:memory: \
KATRAIN_SECRET_KEY=membership-local-test-only \
CI=true PYTHONDONTWRITEBYTECODE=1 \
../katrain-kiosk-debug/.venv/bin/python -m pytest \
  tests/web_ui/test_membership_journeys.py -q --tb=short
```

16 条 warning 均来自现有 `auth.create_access_token` 的 `datetime.utcnow()` 弃用提醒。

## 证据范围

两个客户端代表 Galaxy/kiosk 共享同一 API/account 契约；这不等同于实际 RK 设备、浏览器 UI 或 board 反向代理验收。本轮未执行完整 server lifespan、真实支付商或真实 GPU。受控 TEST 主体只验证资格消费，不能证明正式 P3 验证已实现；当前正式资格依赖仍默认 False。部署健康与实际 Galaxy/kiosk 页面仍属于后续发布验收。
