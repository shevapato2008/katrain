"""Task 2: 限流分桶用的客户端 IP（preflight F10）。

用**真的** `starlette.requests.Request`，不用 `Mock`：
  - `request.client` 是真的 `Address`，"没有对端"那一支是真的 `None` ——
    `Mock` 上随便读一个属性都会自动长出一个真值对象，那条分支在 Mock 里
    很容易写成永远走不到；
  - `request.headers` 是真的 `Headers`（ASGI 规范保证 raw header 名是小写的，
    实现里就该用小写去查）。
"""

import pytest
from starlette.requests import Request

from katrain.web.core.client_ip import client_ip_for_ratelimit


def _req(xff=None, peer="172.20.0.1"):
    headers = [] if xff is None else [(b"x-forwarded-for", xff.encode())]
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": headers,
        "client": (peer, 12345) if peer else None,
    }
    return Request(scope)


def _set_hops(monkeypatch, n):
    """**故意不带 `raising=False`**：字段没加进 `Settings` 时这里当场红。
    带上 `raising=False` 的话，Task 的 config 那一半可以整个没做而测试全绿。"""
    from katrain.web.core import client_ip as m

    monkeypatch.setattr(m.settings, "TRUSTED_PROXY_HOPS", n)


def test_takes_nth_from_right_with_one_hop(monkeypatch):
    _set_hops(monkeypatch, 1)
    # 客户端伪造了两跳，nginx 用 $proxy_add_x_forwarded_for 追加了真实对端 —— 取右起第 1 跳
    assert client_ip_for_ratelimit(_req("1.2.3.4, 5.6.7.8, 203.0.113.9")) == "203.0.113.9"


def test_two_different_clients_get_different_buckets(monkeypatch):
    """**这条是这个 Task 存在的理由。**
    只断言"限流会拦"的用例对 F10 那个缺陷免疫 —— 在"全站一个桶"的世界里它也是绿的。"""
    _set_hops(monkeypatch, 1)
    a = client_ip_for_ratelimit(_req("203.0.113.9"))
    b = client_ip_for_ratelimit(_req("198.51.100.7"))
    assert a != b


def test_falls_back_to_peer_when_no_xff(monkeypatch):
    _set_hops(monkeypatch, 1)
    assert client_ip_for_ratelimit(_req(None, peer="10.0.0.5")) == "10.0.0.5"


def test_hops_larger_than_chain_falls_back_to_leftmost(monkeypatch):
    """链比配置短 —— 不许 IndexError，也不许静默返回对端（那等于全站一个桶）。"""
    _set_hops(monkeypatch, 5)
    assert client_ip_for_ratelimit(_req("203.0.113.9, 198.51.100.7")) == "203.0.113.9"


def test_zero_hops_means_do_not_trust_the_header(monkeypatch):
    _set_hops(monkeypatch, 0)
    assert client_ip_for_ratelimit(_req("203.0.113.9", peer="172.20.0.1")) == "172.20.0.1"


def test_never_returns_empty(monkeypatch):
    _set_hops(monkeypatch, 1)
    assert client_ip_for_ratelimit(_req(", ,")) == "172.20.0.1"          # 全是空段
    assert client_ip_for_ratelimit(_req("203.0.113.9", peer=None)) == "203.0.113.9"
    assert client_ip_for_ratelimit(_req(None, peer=None)) == "unknown"   # 既没头也没对端


def test_settings_default_is_one_hop(monkeypatch):
    """字段真的在 `Settings` 上，默认 1 跳（我们的部署就是 nginx 一层）。"""
    monkeypatch.delenv("KATRAIN_TRUSTED_PROXY_HOPS", raising=False)
    from katrain.web.core.config import Settings

    assert Settings().TRUSTED_PROXY_HOPS == 1


def test_env_var_overrides_hops(monkeypatch):
    """env 装配那一行真的写了。只加字段不加装配的话这条红 ——
    而那种漏法在生产上的表现是"配了没生效"，一声不吭。"""
    monkeypatch.setenv("KATRAIN_TRUSTED_PROXY_HOPS", "0")
    from katrain.web.core.config import Settings

    assert Settings().TRUSTED_PROXY_HOPS == 0
