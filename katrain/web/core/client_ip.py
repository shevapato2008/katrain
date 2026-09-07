"""限流用的客户端 IP。**不要用 `request.client.host`。**

实测（preflight F10）：生产 web 容器在 bridge 网络上，对端恒为网关 172.20.0.1，
而 uvicorn 的 `forwarded_allow_ips` 默认只信 127.0.0.1 且部署未放开
⇒ `request.client.host` 对**每一个用户**都是同一个值。拿它分桶，
全站第 N 个正常用户就被限流挡住，而表现是"限流生效了"，不是报错。

为什么不去放开 `FORWARDED_ALLOW_IPS`：那个值生产是 172.20.0.1、测试是 172.19.0.1，
本来就不是一个数，且 Docker 重建网络后会变 —— 变了之后是**静默**退回全站一个桶。
所以在应用里自己解析，信任跳数写成配置。
"""
from fastapi import Request

from katrain.web.core.config import settings

UNKNOWN = "unknown"


def client_ip_for_ratelimit(request: Request) -> str:
    # 直接读字段，**不用 `getattr(settings, ..., 默认值)` 兜底**：字段没加上时
    # 兜底会把"配置没做"这个错误掩盖成"永远 1 跳"，而它是静默的。
    hops = settings.TRUSTED_PROXY_HOPS
    client = request.client
    peer = (client.host if client is not None else "") or UNKNOWN
    if hops <= 0:
        return peer
    raw = request.headers.get("x-forwarded-for") or ""
    chain = [p.strip() for p in raw.split(",") if p.strip()]
    if not chain:
        return peer
    # 取右起第 hops 跳。右端是最靠近我们的一跳（nginx 用 $proxy_add_x_forwarded_for
    # 追加真实对端），左端是客户端可以随便写的。链比配置短就退到最左 ——
    # 退到对端等于全站一个桶，那正是本模块要避免的。
    idx = max(0, len(chain) - hops)
    return chain[idx]
