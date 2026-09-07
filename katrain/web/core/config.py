import os
import uuid as uuid_module
from pydantic import BaseModel

# 仓库里跟着代码走的字面量默认值。**唯一真源**——生产装配（下方 env 装配处）与
# 字段默认值都引用它，不得各自再抄一份，否则改一处漏一处（参见 assert_secret_key_is_safe）。
INSECURE_DEFAULT_SECRET_KEY = "katrain-secret-key-change-this-in-production"

# HS256 用短密钥可以离线穷举——拿到任意一个 token 就能反推密钥并伪造管理员。
MIN_SECRET_KEY_CHARS = 32


def assert_secret_key_is_safe(mode: str, secret_key: str) -> None:
    """服务端模式下必须显式注入一个**足够长**的密钥。

    盒子（board）跑本地库、不对外签发身份，放行。

    为什么不只挡默认字面量：compose 的 `:?` 只保护 compose 这一条入口。
    直接 `python -m katrain`、systemd、或别的部署路径传进来的空串、空白、
    单字符都会通过，而 HS256 的短密钥可以离线穷举 —— 拿到任意一个 token
    就能反推密钥并伪造管理员。
    """
    if mode != "server":
        return
    if not secret_key or not secret_key.strip():
        raise RuntimeError("拒绝以空 SECRET_KEY 启动服务端：设置 KATRAIN_SECRET_KEY。")
    if len(secret_key.strip()) < MIN_SECRET_KEY_CHARS:
        raise RuntimeError(
            f"SECRET_KEY 太短（{len(secret_key.strip())} 字符，至少 {MIN_SECRET_KEY_CHARS}）："
            "HS256 短密钥可离线穷举。用 `python -c \"import secrets;print(secrets.token_urlsafe(48))\"` 生成。"
        )
    if secret_key == INSECURE_DEFAULT_SECRET_KEY:
        raise RuntimeError(
            "拒绝以内置默认 SECRET_KEY 启动服务端：任何人都能用仓库里的字面量伪造任意用户的 token。"
            "请设置环境变量 KATRAIN_SECRET_KEY（建议 `python -c \"import secrets;print(secrets.token_urlsafe(48))\"`）。"
        )


# `sms.get_provider()` 认得的全部名字。**唯一真源** —— 启动闸只放行这里面的名字，
# 否则"闸放行了一个工厂造不出来的名字"会一路活到第一个用户点发送。
KNOWN_SMS_PROVIDERS = ("console", "aliyun")


def assert_sms_provider_is_configured(mode: str, provider: str, allow_console: bool = False) -> None:
    """服务端模式下必须显式选一个**真**提供方。

    为什么不让 console 在生产兜底：那会让 send-code 一路返回 200 而用户
    **永远收不到码** —— 一种"坏了"和"好着"在用户那里长得一模一样的故障
    （spec §2.1）。盒子不发短信（四个端点在盒子上 403/503），放行。

    为什么未知名也拒：`KATRAIN_SMS_PROVIDER=aliyu` 这种手滑今天能正常启动，
    直到第一个用户点"发送验证码"才在 get_provider() 里炸成 502。
    启动期判得了的事，不要留到请求期。
    """
    if mode != "server":
        return
    name = (provider or "").strip()
    if not name:
        raise RuntimeError(
            "拒绝以未配置的 SMS_PROVIDER 启动服务端：设置 KATRAIN_SMS_PROVIDER=aliyun。"
        )
    # console 的**显式**放行口。Global Constraint #3 禁的是「静默生效」——
    # 一个默认关、必须专门去设的 env 不是静默；而没有它，本机真浏览器验收
    # 根本读不到验证码（表里只存 code_hash，aliyun 空凭据必 502）⇒ 那一整关做不了。
    # 生产两台机器都不设它，闸照旧拒 console。
    if name == "console" and not allow_console:
        raise RuntimeError(
            "拒绝在服务端使用 console 短信提供方：它只打印不发送，"
            "接口会一路返回成功而用户永远收不到码。"
            "本机开发请用 KATRAIN_MODE=board 或直接跑单测。"
        )
    if name not in KNOWN_SMS_PROVIDERS:
        raise RuntimeError(
            f"未知的 SMS_PROVIDER={name!r}：可选 {list(KNOWN_SMS_PROVIDERS)}。"
            "（KATRAIN_SMS_PROVIDER 拼错时，启动期不拒就要等第一个用户去发现。）"
        )


class Settings(BaseModel):
    PROJECT_NAME: str = "KaTrain Web UI"
    VERSION: str = "1.17.1"
    API_V1_STR: str = "/api/v1"

    KATRAIN_HOST: str = "0.0.0.0"
    KATRAIN_PORT: int = 8001

    SESSION_TIMEOUT: int = 3600
    MAX_SESSIONS: int = 100

    # Engine Settings
    LOCAL_KATAGO_URL: str = "http://127.0.0.1:8000"
    CLOUD_KATAGO_URL: str = ""

    # Persistence
    DATABASE_PATH: str = "db.sqlite3"
    DATABASE_URL: str = "sqlite:///./db.sqlite3"

    # Media storage (tutorial video/audio/page images). See
    # superpowers/tracks/tutorial-database/plan.md.
    STORAGE_BACKEND: str = "local"          # local | s3
    S3_ENDPOINT_URL: str = ""               # MinIO: http://minio:9000 ; OSS: https://oss-cn-<region>.aliyuncs.com
    S3_REGION: str = ""                     # OSS: cn-hangzhou ...; MinIO can be blank
    S3_BUCKET: str = "tutorial-assets"
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_PUBLIC_BASE_URL: str = ""            # client-reachable prefix: phase1 nginx domain; phase2 CDN domain
    S3_USE_PRESIGNED: bool = False          # private bucket -> public_url() returns a signed URL
    S3_PRESIGN_TTL_SEC: int = 3600

    # Security
    SECRET_KEY: str = INSECURE_DEFAULT_SECRET_KEY
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    REFRESH_TOKEN_EXPIRE_DAYS: int = 90

    # 限流分桶取 X-Forwarded-For 右起第几跳。见 core/client_ip.py（preflight F10）。
    # 我们的部署是 nginx 一层 ⇒ 1。0 = 完全不信任该头，退回 request.client.host
    # （只有在**没有**反向代理时才对）。
    TRUSTED_PROXY_HOPS: int = 1

    # 空库首次启动时创建管理员账号用的口令。**默认空 = 不创建任何账号**。
    # 从环境注入（KATRAIN_ADMIN_BOOTSTRAP_PASSWORD），用完即应清掉。
    ADMIN_BOOTSTRAP_PASSWORD: str = ""

    DEFAULT_LANG: str = "cn"

    # Board mode settings (see design.md Section 4.2)
    KATRAIN_MODE: str = "server"  # "server" or "board"
    REMOTE_API_URL: str = ""  # Remote server URL for board mode, e.g. "https://katrain.example.com"
    DEVICE_ID: str = ""  # Unique device identifier, auto-generated if empty
    KATRAIN_BOX_SSO: bool = False
    KATRAIN_BOX_SSO_BRIDGE_KEY_PATH: str = "/etc/smartbox/box-sso-bridge.key"

    # Billing / paid-analysis (single-pool integer credits). Prices are per analysis action.
    BILLING_PRICES: dict = {"territory": 10, "hints": 10, "variations": 10}
    BILLING_PACKAGES: list = [
        {"package_id": "p6", "credits": 600, "amount_fen": 600, "title": "6 元 600 积分"},
        {"package_id": "p30", "credits": 3300, "amount_fen": 3000, "title": "30 元 3300 积分"},
        {"package_id": "p98", "credits": 12000, "amount_fen": 9800, "title": "98 元 12000 积分"},
    ]
    # 注册赠额（>0 才发）。走 billing.grant，写一条可审计的账本行 —— 不是列默认值。
    BILLING_SIGNUP_GRANT: int = 0
    BILLING_RESERVATION_TTL_SEC: int = 120  # stale 'reserved' refund threshold
    REDEEM_RATE_LIMIT: int = 5  # max failed redeem attempts / user / minute

    # 计费总闸。默认关 —— 打开的前置见 superpowers/tracks/galaxy-payment/plan.md 的
    # Global Constraints（P3 手机绑定+注册限流 / P5 合规页脚 / U4 经营资质定性）。
    # 关着时 POST /api/v1/reports/ 的行为必须与今天逐字节一致：不扣费、不消费额度、不返 402。
    #
    # ⚠️ 「P3 手机绑定 + 注册限流」是**硬前置**，不是"尽量"：
    # 免费复盘桶的键是 user_id（不是手机号），而 /auth/register 至今无验证码无限流
    # ⇒ 注册 N 个用户名 = 每周 N 份免费复盘 = N × 约 125 credits 的 GPU。
    # 若 P3 未落地就要开这个闸，必须同时把 FREE_WEEKLY_REPORTS 配成 0。
    BILLING_ENFORCED: bool = False
    # 每周免费复盘次数（裁决 D2）。不滚存 —— 见 katrain/web/core/quota.py。
    FREE_WEEKLY_REPORTS: int = 1
    # failed 任务的重试宽限期：宽限期内 /retry 复用原预扣，不重新授权。
    # 过了宽限期，结算器会把这笔预扣按 analyzed_moves 结掉 —— 之后再 /retry
    # 就必须重新预扣剩余手数（见 report_settlement.py / reports.py:/retry）。
    REPORT_RETRY_GRACE_SEC: int = 3600

    # --- 短信 -----------------------------------------------------------
    SMS_PROVIDER: str = ""                 # console | aliyun；服务端为空即拒绝启动
    SMS_ACCESS_KEY_ID: str = ""
    SMS_ACCESS_KEY_SECRET: str = ""
    SMS_SIGN_NAME: str = "万智星"           # 【智星盒】不可用，见 spec §2.10
    SMS_TEMPLATE_CODE: str = ""
    SMS_CODE_TTL_SEC: int = 300
    SMS_COOLDOWN_SEC: int = 60
    SMS_PHONE_HOURLY: int = 5              # 比阿里云官方流控（5 条/小时）不松
    SMS_PHONE_DAILY: int = 10
    SMS_IP_DAILY: int = 20
    SMS_MAX_ATTEMPTS: int = 5
    # 全站日额度。**两个独立常数，不是"一个 cap 加一个比例"** —— 比例是式子，
    # 调其中一个会静默改另一个；两个独立常数改哪个就是哪个。
    # 定标依据（写在这里，免得后人以为是拍的）：
    #   国内 300：上线首月峰值按 100 个新注册/日 × 1.6 条（含一次重发）≈ 160，
    #            留约 2 倍余量；按 ~¥0.045/条 ⇒ **封顶约 ¥13.5/日**。
    #   国际  50：单价按最坏目的地约 $0.15/条 ⇒ **封顶约 $7.5/日**。国际号是长尾
    #            （要求是"要能绑"不是"主力市场"），却是**最贵的攻击面** ——
    #            所以封顶必须比国内低一个量级，不是低三成。
    # 选这两个数的判据不是"够用"，是**上限被打满时的损失，是我们愿意在没人值班的
    # 夜里承受的**。requirements §3 D-U4 那张表写的是 300 / 100，且那一行自己标着
    # 「⚠️ 待核 …… 实现时以最终值为准」——**这里就是那个最终值**：国内取 300
    # （与需求一致），国际取两个候选里更低的 50。两个都能用下面的 env 覆盖，
    # 改数不需要改代码。
    SMS_DAILY_CAP_CN: int = 300
    SMS_DAILY_CAP_INTL: int = 50
    # console 的显式放行口。**生产两台机器都不设**，只在本机真浏览器验收时开。
    SMS_ALLOW_CONSOLE: bool = False
    # /auth/register 的 per-IP 日限（D-U2：建了限流器就要给那个已知无限流的端点用）。
    # 消费者在 Task 7；声明必须在这里，否则 Settings 是 pydantic BaseModel，读不存在的
    # 属性直接抛，而 monkeypatch 也设不上（raising=False 只跳过存在性预检）。
    REGISTER_IP_DAILY: int = 10

    def __init__(self, **data):
        # Override with env vars if not provided in data
        data.setdefault("KATRAIN_HOST", os.getenv("KATRAIN_HOST", "0.0.0.0"))
        data.setdefault("KATRAIN_PORT", int(os.getenv("KATRAIN_PORT", 8001)))
        data.setdefault("SESSION_TIMEOUT", int(os.getenv("KATRAIN_SESSION_TIMEOUT", 3600)))
        data.setdefault("MAX_SESSIONS", int(os.getenv("KATRAIN_MAX_SESSIONS", 100)))
        data.setdefault("LOCAL_KATAGO_URL", os.getenv("LOCAL_KATAGO_URL", "http://127.0.0.1:8000"))
        data.setdefault("CLOUD_KATAGO_URL", os.getenv("CLOUD_KATAGO_URL", ""))
        data.setdefault("DATABASE_PATH", os.getenv("KATRAIN_DATABASE_PATH", "db.sqlite3"))

        # New DATABASE_URL support
        env_db_url = os.getenv("KATRAIN_DATABASE_URL")
        if env_db_url:
            data["DATABASE_URL"] = env_db_url
        else:
            # Try to load from config.json
            import json
            from pathlib import Path

            try:
                # Check standard locations: ~/.katrain/config.json or ./katrain/config.json
                config_paths = [Path.home() / ".katrain" / "config.json", Path("katrain/config.json")]
                json_db_url = None
                for path in config_paths:
                    if path.exists():
                        with open(path, "r", encoding="utf-8") as f:
                            config_data = json.load(f)
                            # Check for "server": {"database_url": "..."}
                            if "server" in config_data and "database_url" in config_data["server"]:
                                json_db_url = config_data["server"]["database_url"]
                                break

                if json_db_url:
                    data["DATABASE_URL"] = json_db_url
                else:
                    # Fallback to sqlite using the DATABASE_PATH
                    data.setdefault("DATABASE_URL", f"sqlite:///./{data.get('DATABASE_PATH', 'db.sqlite3')}")
            except Exception as e:
                print(f"Warning: Failed to read config.json: {e}")
                # Fallback to sqlite using the DATABASE_PATH
                data.setdefault("DATABASE_URL", f"sqlite:///./{data.get('DATABASE_PATH', 'db.sqlite3')}")

        # Media storage settings
        data.setdefault("STORAGE_BACKEND", os.getenv("KATRAIN_STORAGE_BACKEND", "local"))
        data.setdefault("S3_ENDPOINT_URL", os.getenv("KATRAIN_S3_ENDPOINT_URL", ""))
        data.setdefault("S3_REGION", os.getenv("KATRAIN_S3_REGION", ""))
        data.setdefault("S3_BUCKET", os.getenv("KATRAIN_S3_BUCKET", "tutorial-assets"))
        data.setdefault("S3_ACCESS_KEY", os.getenv("KATRAIN_S3_ACCESS_KEY", ""))
        data.setdefault("S3_SECRET_KEY", os.getenv("KATRAIN_S3_SECRET_KEY", ""))
        data.setdefault("S3_PUBLIC_BASE_URL", os.getenv("KATRAIN_S3_PUBLIC_BASE_URL", ""))
        data.setdefault("S3_USE_PRESIGNED", os.getenv("KATRAIN_S3_USE_PRESIGNED", "false").lower() in ("1", "true", "yes"))

        data.setdefault("SECRET_KEY", os.getenv("KATRAIN_SECRET_KEY", INSECURE_DEFAULT_SECRET_KEY))
        data.setdefault("ADMIN_BOOTSTRAP_PASSWORD", os.getenv("KATRAIN_ADMIN_BOOTSTRAP_PASSWORD", ""))
        data.setdefault("DEFAULT_LANG", os.getenv("KATRAIN_DEFAULT_LANG", "cn"))

        # Board mode settings
        data.setdefault("KATRAIN_MODE", os.getenv("KATRAIN_MODE", "server"))
        data.setdefault("REMOTE_API_URL", os.getenv("KATRAIN_REMOTE_URL", ""))
        data.setdefault(
            "KATRAIN_BOX_SSO",
            os.getenv("KATRAIN_BOX_SSO", "0").lower() in ("1", "true", "yes"),
        )
        data.setdefault(
            "KATRAIN_BOX_SSO_BRIDGE_KEY_PATH",
            os.getenv(
                "KATRAIN_BOX_SSO_BRIDGE_KEY_PATH",
                "/etc/smartbox/box-sso-bridge.key",
            ),
        )
        device_id = os.getenv("KATRAIN_DEVICE_ID", "")
        if not device_id:
            device_id = uuid_module.uuid4().hex
        data.setdefault("DEVICE_ID", device_id)
        data.setdefault("REFRESH_TOKEN_EXPIRE_DAYS", int(os.getenv("KATRAIN_REFRESH_TOKEN_EXPIRE_DAYS", 90)))
        data.setdefault("TRUSTED_PROXY_HOPS", int(os.getenv("KATRAIN_TRUSTED_PROXY_HOPS", 1)))

        # 短信。字段声明 + 这里的 env 装配是两件事，缺一个就"env 设了不生效"。
        data.setdefault("SMS_PROVIDER", os.getenv("KATRAIN_SMS_PROVIDER", ""))
        data.setdefault("SMS_ALLOW_CONSOLE", os.getenv("KATRAIN_SMS_ALLOW_CONSOLE", "") == "1")
        data.setdefault("REGISTER_IP_DAILY", int(os.getenv("KATRAIN_REGISTER_IP_DAILY", 10)))
        data.setdefault("SMS_ACCESS_KEY_ID", os.getenv("KATRAIN_SMS_ACCESS_KEY_ID", ""))
        data.setdefault("SMS_ACCESS_KEY_SECRET", os.getenv("KATRAIN_SMS_ACCESS_KEY_SECRET", ""))
        data.setdefault("SMS_SIGN_NAME", os.getenv("KATRAIN_SMS_SIGN_NAME", "万智星"))
        data.setdefault("SMS_TEMPLATE_CODE", os.getenv("KATRAIN_SMS_TEMPLATE_CODE", ""))
        data.setdefault("SMS_CODE_TTL_SEC", int(os.getenv("KATRAIN_SMS_CODE_TTL_SEC", 300)))
        data.setdefault("SMS_COOLDOWN_SEC", int(os.getenv("KATRAIN_SMS_COOLDOWN_SEC", 60)))
        data.setdefault("SMS_PHONE_HOURLY", int(os.getenv("KATRAIN_SMS_PHONE_HOURLY", 5)))
        data.setdefault("SMS_PHONE_DAILY", int(os.getenv("KATRAIN_SMS_PHONE_DAILY", 10)))
        data.setdefault("SMS_IP_DAILY", int(os.getenv("KATRAIN_SMS_IP_DAILY", 20)))
        data.setdefault("SMS_MAX_ATTEMPTS", int(os.getenv("KATRAIN_SMS_MAX_ATTEMPTS", 5)))
        data.setdefault("SMS_DAILY_CAP_CN", int(os.getenv("KATRAIN_SMS_DAILY_CAP_CN", 300)))
        data.setdefault("SMS_DAILY_CAP_INTL", int(os.getenv("KATRAIN_SMS_DAILY_CAP_INTL", 50)))

        # Board mode always uses local SQLite — ignore any PostgreSQL URL from config.json
        if data.get("KATRAIN_MODE") == "board" and not os.getenv("KATRAIN_DATABASE_URL"):
            db_path = data.get("DATABASE_PATH", "db.sqlite3")
            data["DATABASE_URL"] = f"sqlite:///./{db_path}"

        super().__init__(**data)


settings = Settings()
