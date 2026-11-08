"""Protocol tests use disposable keys and a transport which cannot reach a merchant."""

import base64
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import re
from types import SimpleNamespace

import httpx
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from katrain.web.core import wechat_native as wx


NOW = 1794096000
ORDER = "WX_order|*123"


@pytest.fixture(scope="module")
def keys():
    return tuple(rsa.generate_private_key(public_exponent=65537, key_size=2048) for _ in range(2))


@pytest.fixture
def cfg(tmp_path, keys):
    merchant, provider = keys
    private = tmp_path / "merchant.pem"
    private.write_bytes(
        merchant.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
        )
    )
    public = tmp_path / "provider.pem"
    public.write_bytes(
        provider.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    )
    api = tmp_path / "apiv3.key"
    api.write_bytes(b"temporary-test-api-v3-key-32-byt")
    assert len(api.read_bytes()) == 32
    return SimpleNamespace(
        WECHAT_PAY_APP_ID="wx1234567890abcdef",
        WECHAT_PAY_MCH_ID="1234567890",
        WECHAT_PAY_MERCHANT_SERIAL="ABCDEF0123456789",
        WECHAT_PAY_PRIVATE_KEY_PATH=str(private),
        WECHAT_PAY_API_V3_KEY_PATH=str(api),
        WECHAT_PAY_PUBLIC_KEY_ID="PUB_KEY_ID_TEST_123",
        WECHAT_PAY_PUBLIC_KEY_PATH=str(public),
        WECHAT_PAY_NOTIFY_URL="https://merchant.example/pay/notify",
    )


def signed(provider, body, *, timestamp=NOW, serial="PUB_KEY_ID_TEST_123", nonce="provider-nonce"):
    canonical = f"{timestamp}\n{nonce}\n".encode() + body + b"\n"
    signature = provider.sign(canonical, padding.PKCS1v15(), hashes.SHA256())
    return {
        "Wechatpay-Timestamp": str(timestamp),
        "Wechatpay-Nonce": nonce,
        "Wechatpay-Serial": serial,
        "Wechatpay-Signature": base64.b64encode(signature).decode(),
    }


def request_payload(cfg):
    return {
        "appid": cfg.WECHAT_PAY_APP_ID,
        "mchid": cfg.WECHAT_PAY_MCH_ID,
        "description": "会员与充值",
        "out_trade_no": ORDER,
        "notify_url": cfg.WECHAT_PAY_NOTIFY_URL,
        "time_expire": "2026-11-08T16:15:00+08:00",
        "amount": {"total": 600, "currency": "CNY"},
    }


def client(cfg, handler):
    return wx.WechatNativeClient.from_settings(cfg, transport=httpx.MockTransport(handler), clock=lambda: NOW)


def test_settings_default_disabled_and_file_only_config_is_redacted(cfg, monkeypatch):
    from katrain.web.core.config import Settings

    monkeypatch.delenv("PAYMENTS_MODE", raising=False)
    settings = Settings(**vars(cfg))
    assert settings.PAYMENTS_MODE == "disabled"
    assert Settings(PAYMENTS_MODE="live").PAYMENTS_MODE == "live"
    assert cfg.WECHAT_PAY_API_V3_KEY_PATH not in repr(settings)
    loaded = wx.WechatNativeConfig.from_settings(settings)
    assert loaded.app_id == cfg.WECHAT_PAY_APP_ID
    assert loaded.mch_id == cfg.WECHAT_PAY_MCH_ID
    assert "temporary-test-api" not in repr(loaded)
    with pytest.raises(FrozenInstanceError):
        loaded.mch_id = "changed"
    assert wx.wechat_native_ready(settings)
    assert not wx.wechat_native_ready(SimpleNamespace())


@pytest.mark.parametrize(
    "field,value",
    [
        ("WECHAT_PAY_PRIVATE_KEY_PATH", "/missing/payment-private-key"),
        ("WECHAT_PAY_PUBLIC_KEY_ID", "arbitrary-certificate-serial"),
        ("WECHAT_PAY_NOTIFY_URL", "http://merchant.example/notify"),
        ("WECHAT_PAY_NOTIFY_URL", "https://merchant.example/notify?query=1"),
        ("WECHAT_PAY_MERCHANT_SERIAL", "serial\nheader"),
    ],
)
def test_bad_config_fails_closed_without_exposing_values(cfg, field, value):
    setattr(cfg, field, value)
    assert not wx.wechat_native_ready(cfg)
    with pytest.raises(wx.WechatConfigurationError) as error:
        wx.WechatNativeClient.from_settings(cfg)
    assert error.value.code == "configuration_invalid"
    assert value not in str(error.value)


def test_create_signs_the_exact_json_bytes_and_selects_configured_public_key(cfg, keys):
    def handle(request):
        assert request.url.scheme == "https" and request.url.host == "api.mch.weixin.qq.com"
        assert request.headers["Wechatpay-Serial"] == cfg.WECHAT_PAY_PUBLIC_KEY_ID
        assert request.method == "POST" and request.url.raw_path == b"/v3/pay/transactions/native"
        assert json.loads(request.content) == request_payload(cfg)
        auth = request.headers["authorization"]
        assert auth.startswith("WECHATPAY2-SHA256-RSA2048 ")
        fields = dict(re.findall(r'(\w+)="([^"]*)"', auth))
        assert fields["mchid"] == cfg.WECHAT_PAY_MCH_ID
        assert fields["serial_no"] == cfg.WECHAT_PAY_MERCHANT_SERIAL
        canonical = (
            b"POST\n"
            + request.url.raw_path
            + b"\n"
            + fields["timestamp"].encode()
            + b"\n"
            + fields["nonce_str"].encode()
            + b"\n"
            + request.content
            + b"\n"
        )
        keys[0].public_key().verify(
            base64.b64decode(fields["signature"]), canonical, padding.PKCS1v15(), hashes.SHA256()
        )
        body = b'{ "code_url" : "weixin://wxpay/bizpayurl?pr=TestNative" }'
        return httpx.Response(200, content=body, headers=signed(keys[1], body))

    assert client(cfg, handle).create_native(request_payload(cfg)) == "weixin://wxpay/bizpayurl?pr=TestNative"


def test_query_signs_the_encoded_url_and_close_verifies_empty_204(cfg, keys):
    def handle(request):
        assert request.url.raw_path == (
            b"/v3/pay/transactions/out-trade-no/WX_order%7C%2A123"
            + (b"/close" if request.method == "POST" else b"?mchid=1234567890")
        )
        fields = dict(re.findall(r'(\w+)="([^"]*)"', request.headers["authorization"]))
        canonical = (
            request.method.encode()
            + b"\n"
            + request.url.raw_path
            + b"\n"
            + fields["timestamp"].encode()
            + b"\n"
            + fields["nonce_str"].encode()
            + b"\n"
            + request.content
            + b"\n"
        )
        keys[0].public_key().verify(
            base64.b64decode(fields["signature"]), canonical, padding.PKCS1v15(), hashes.SHA256()
        )
        if request.method == "GET":
            assert request.content == b""
            body = b'{ "trade_state": "NOTPAY" }\n'
            return httpx.Response(200, content=body, headers=signed(keys[1], body))
        assert json.loads(request.content) == {"mchid": cfg.WECHAT_PAY_MCH_ID}
        return httpx.Response(204, headers=signed(keys[1], b""))

    api = client(cfg, handle)
    assert api.query(ORDER) == {"trade_state": "NOTPAY"}
    assert api.close(ORDER) is None


@pytest.mark.parametrize("mode", ["unsigned", "wrong_key", "wrong_serial", "old", "future", "tamper", "probe"])
@pytest.mark.parametrize("operation", ["query", "close"])
def test_success_responses_reject_unsigned_invalid_or_stale_signatures(cfg, keys, mode, operation):
    body = b'{"trade_state":"SUCCESS"}' if operation == "query" else b""
    headers = signed(
        keys[0] if mode == "wrong_key" else keys[1],
        body,
        timestamp=NOW - 301 if mode == "old" else NOW + 301 if mode == "future" else NOW,
        serial="PUB_KEY_ID_UNKNOWN" if mode == "wrong_serial" else cfg.WECHAT_PAY_PUBLIC_KEY_ID,
    )
    if mode == "unsigned":
        headers = {}
    if mode == "probe":
        headers["Wechatpay-Signature"] = "WECHATPAY/SIGNTEST/invalid"
    if mode == "tamper":
        body += b" "
    api = client(cfg, lambda req: httpx.Response(200 if operation == "query" else 204, content=body, headers=headers))
    with pytest.raises(wx.WechatNativeError) as error:
        getattr(api, operation)(ORDER)
    assert error.value.code == "invalid_signature"


@pytest.mark.parametrize("status", [302, 404, 500])
def test_unsigned_non_success_is_never_authoritative_and_error_is_sanitized(cfg, status):
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(
            status,
            content=b'{"code":"ORDER_NOT_EXIST","secret":"upstream-private-body"}',
            headers={"location": "https://other.example/"},
        )

    with pytest.raises(wx.WechatNativeError) as error:
        client(cfg, handle).close(ORDER)
    assert len(calls) == 1
    assert error.value.code == "provider_error" and error.value.status_code == status
    assert "upstream-private-body" not in str(error.value)


def test_signed_error_is_verified_and_transport_timeout_is_ambiguous(cfg, keys):
    body = b'{"code":"SYSTEM_ERROR"}'
    headers = signed(keys[0], body)
    with pytest.raises(wx.WechatNativeError, match="invalid_signature"):
        client(cfg, lambda req: httpx.Response(500, content=body, headers=headers)).query(ORDER)

    def timeout(request):
        raise httpx.ReadTimeout("secret upstream detail", request=request)

    with pytest.raises(wx.WechatNativeError) as error:
        client(cfg, timeout).create_native(request_payload(cfg))
    assert error.value.code == "transport_error"
    assert "secret" not in str(error.value)


def notification(cfg, keys, *, resource_update=None, envelope_update=None):
    transaction = {
        "appid": cfg.WECHAT_PAY_APP_ID,
        "mchid": cfg.WECHAT_PAY_MCH_ID,
        "out_trade_no": ORDER,
        "trade_state": "SUCCESS",
        "trade_type": "NATIVE",
        "transaction_id": "42000000000001",
        "success_time": "2026-11-08T16:01:00+08:00",
        "amount": {"total": 600, "payer_total": 500, "currency": "CNY"},
    }
    ciphertext = AESGCM(b"temporary-test-api-v3-key-32-byt").encrypt(
        b"testnonce123", json.dumps(transaction).encode(), b"transaction"
    )
    resource = {
        "algorithm": "AEAD_AES_256_GCM",
        "original_type": "transaction",
        "nonce": "testnonce123",
        "associated_data": "transaction",
        "ciphertext": base64.b64encode(ciphertext).decode(),
    }
    resource.update(resource_update or {})
    envelope = {
        "id": "event-test-id",
        "event_type": "TRANSACTION.SUCCESS",
        "resource_type": "encrypt-resource",
        "resource": resource,
    }
    envelope.update(envelope_update or {})
    body = json.dumps(envelope, ensure_ascii=False, indent=2).encode()
    return signed(keys[1], body), body, transaction


def test_notification_verifies_original_bytes_then_authenticated_decryption(cfg, keys):
    headers, body, transaction = notification(cfg, keys)
    api = client(cfg, lambda req: pytest.fail("notification decode must not access network"))
    assert api.decode_notification(headers, body) == transaction
    assert api.decode_notification({key.lower(): value for key, value in headers.items()}, body) == transaction
    with pytest.raises(wx.WechatNativeError, match="invalid_signature"):
        api.decode_notification(headers, json.dumps(json.loads(body)).encode())


@pytest.mark.parametrize("change", ["ciphertext", "tag", "associated_data", "nonce", "algorithm", "event"])
def test_notification_rejects_bad_authenticated_resource_or_event(cfg, keys, change):
    resource, envelope = {}, {}
    if change == "event":
        envelope["event_type"] = "REFUND.SUCCESS"
    elif change == "tag":
        _, body, _ = notification(cfg, keys)
        raw = bytearray(base64.b64decode(json.loads(body)["resource"]["ciphertext"]))
        raw[-1] ^= 1
        resource["ciphertext"] = base64.b64encode(raw).decode()
    else:
        resource[change] = {
            "ciphertext": "not-base64",
            "associated_data": "changed",
            "nonce": "short",
            "algorithm": "unsupported",
        }[change]
    headers, body, _ = notification(cfg, keys, resource_update=resource, envelope_update=envelope)
    with pytest.raises(wx.WechatNativeError, match="invalid_payload"):
        client(cfg, lambda req: pytest.fail("no network")).decode_notification(headers, body)


@pytest.mark.parametrize("change", ["amount_bool", "order_path", "notify", "appid", "binding", "expiry", "too_long"])
def test_invalid_native_fields_never_reach_transport(cfg, change):
    payload = request_payload(cfg)
    if change == "amount_bool":
        payload["amount"]["total"] = True
    elif change == "order_path":
        payload["out_trade_no"] = "../other?mchid=attacker"
    elif change == "notify":
        payload["notify_url"] = "http://merchant.example/notify"
    elif change == "appid":
        payload["appid"] = "invalid\nAppID"
    elif change == "binding":
        payload["mchid"] = "9999999999"
    elif change == "expiry":
        payload["time_expire"] = "2026-11-08T16:00:00"
    else:
        payload["description"] = "x" * 128
    with pytest.raises(wx.WechatNativeError, match="invalid_payload"):
        client(cfg, lambda req: pytest.fail("invalid request sent")).create_native(payload)


def test_bounded_response_and_notification_body(cfg, keys):
    body = b"x" * (wx.MAX_BODY_BYTES + 1)
    with pytest.raises(wx.WechatNativeError, match="invalid_payload"):
        client(cfg, lambda req: httpx.Response(200, content=body)).query(ORDER)
    with pytest.raises(wx.WechatNativeError, match="invalid_payload"):
        client(cfg, lambda req: pytest.fail("no network")).decode_notification(signed(keys[1], body), body)


def test_config_reloads_changed_files_and_does_not_cache_configuration_failures(cfg, keys):
    original = wx.WechatNativeConfig.from_settings(cfg)
    key_path = Path(cfg.WECHAT_PAY_API_V3_KEY_PATH)
    key_path.write_bytes(b"invalid-length")
    assert not wx.wechat_native_ready(cfg)
    key_path.write_bytes(b"replacement-test-key-for-aes-gcm")
    assert len(key_path.read_bytes()) == 32
    loaded = wx.WechatNativeConfig.from_settings(cfg)
    assert loaded.api_v3_key != original.api_v3_key
    assert wx.wechat_native_ready(cfg)


@pytest.mark.parametrize("kind", ["short_api_key", "weak_private_key", "weak_provider_key", "non_rsa"])
def test_config_rejects_wrong_key_lengths_and_algorithms(cfg, keys, kind):
    from cryptography.hazmat.primitives.asymmetric import ec

    if kind == "short_api_key":
        Path(cfg.WECHAT_PAY_API_V3_KEY_PATH).write_bytes(b"short")
    elif kind == "weak_provider_key":
        weak = rsa.generate_private_key(public_exponent=65537, key_size=1024)
        Path(cfg.WECHAT_PAY_PUBLIC_KEY_PATH).write_bytes(
            weak.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        )
    else:
        key = (
            ec.generate_private_key(ec.SECP256R1())
            if kind == "non_rsa"
            else rsa.generate_private_key(public_exponent=65537, key_size=1024)
        )
        Path(cfg.WECHAT_PAY_PRIVATE_KEY_PATH).write_bytes(
            key.private_bytes(
                serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
            )
        )
    assert not wx.wechat_native_ready(cfg)


@pytest.mark.parametrize("kind", ["old", "future", "serial", "nonce", "probe", "base64"])
def test_notification_rejects_untrusted_signature_headers(cfg, keys, kind):
    headers, body, _ = notification(cfg, keys)
    changes = {
        "old": ("Wechatpay-Timestamp", str(NOW - 301)),
        "future": ("Wechatpay-Timestamp", str(NOW + 301)),
        "serial": ("Wechatpay-Serial", "PUB_KEY_ID_UNKNOWN"),
        "nonce": ("Wechatpay-Nonce", "x" * 257),
        "probe": ("Wechatpay-Signature", "WECHATPAY/SIGNTEST/probe"),
        "base64": ("Wechatpay-Signature", "invalid-base64!"),
    }
    key, value = changes[kind]
    headers[key] = value
    with pytest.raises(wx.WechatNativeError, match="invalid_signature"):
        client(cfg, lambda req: pytest.fail("no network")).decode_notification(headers, body)


@pytest.mark.parametrize("offset", [-300, 300])
def test_signature_clock_window_is_inclusive(cfg, keys, offset):
    body = b'{"trade_state":"NOTPAY"}'
    api = client(
        cfg, lambda req: httpx.Response(200, content=body, headers=signed(keys[1], body, timestamp=NOW + offset))
    )
    assert api.query(ORDER)["trade_state"] == "NOTPAY"


def test_create_requires_rfc3339_expiry_not_only_python_isoformat(cfg):
    request = request_payload(cfg)
    request["time_expire"] = "20261108T161500+0800"
    with pytest.raises(wx.WechatNativeError, match="invalid_payload"):
        client(cfg, lambda req: pytest.fail("invalid timestamp sent")).create_native(request)


def test_streamed_response_limit_stops_reading_unbounded_body(cfg):
    class EndlessBody(httpx.SyncByteStream):
        def __iter__(self):
            for _ in range(20):
                yield b"x" * 8192
            pytest.fail("unbounded stream was fully consumed")

    with pytest.raises(wx.WechatNativeError, match="invalid_payload"):
        client(cfg, lambda req: httpx.Response(200, stream=EndlessBody())).query(ORDER)


@pytest.mark.parametrize(
    "code_url",
    [
        "weixin://wxpay/bizpayurl/up?pr=NwY5Mz9&groupid=00",
        "weixin://pay.weixin.qq.com/bizpayurl/up?pr=NwY5Mz9&groupid=00",
        "weixin://wxpay/bizpayurl?pr=JyC91EIz1",
    ],
)
def test_create_preserves_official_native_code_url_variants(cfg, keys, code_url):
    body = json.dumps({"code_url": code_url}).encode()
    api = client(cfg, lambda req: httpx.Response(200, content=body, headers=signed(keys[1], body)))
    assert api.create_native(request_payload(cfg)) == code_url


@pytest.mark.parametrize("code_url", ["https://untrusted.example/pay", "weixin://", "weixin://wxpay/\ncode"])
def test_create_rejects_malformed_qr_payloads(cfg, keys, code_url):
    body = json.dumps({"code_url": code_url}).encode()
    with pytest.raises(wx.WechatNativeError, match="invalid_payload"):
        client(cfg, lambda req: httpx.Response(200, content=body, headers=signed(keys[1], body))).create_native(
            request_payload(cfg)
        )


def test_slow_drip_response_exceeds_overall_budget_without_receiving_full_body(cfg, monkeypatch):
    elapsed = [0.0]
    monkeypatch.setattr(wx.time, "monotonic", lambda: elapsed[0])

    class SlowBody(httpx.SyncByteStream):
        def __iter__(self):
            for _ in range(20):
                elapsed[0] += 4.0
                yield b"x"
            pytest.fail("drip response was read indefinitely")

    with pytest.raises(wx.WechatNativeError, match="transport_error"):
        client(cfg, lambda req: httpx.Response(200, stream=SlowBody())).query(ORDER)


@pytest.mark.parametrize("changed", ["appid", "notify_url", "both"])
def test_recovery_preserves_frozen_appid_and_callback_after_same_merchant_config_rotation(cfg, keys, changed):
    frozen = request_payload(cfg)
    if changed in {"appid", "both"}:
        cfg.WECHAT_PAY_APP_ID = "wxabcdef1234567890"
    if changed in {"notify_url", "both"}:
        cfg.WECHAT_PAY_NOTIFY_URL = "https://merchant.example/pay/notify-v2"

    def handle(request):
        assert json.loads(request.content) == frozen
        fields = dict(re.findall(r'(\w+)="([^"]*)"', request.headers["authorization"]))
        assert fields["mchid"] == frozen["mchid"]
        body = b'{"code_url":"weixin://wxpay/bizpayurl/up?pr=original-order"}'
        return httpx.Response(200, content=body, headers=signed(keys[1], body))

    assert client(cfg, handle).create_native(frozen) == "weixin://wxpay/bizpayurl/up?pr=original-order"
    assert frozen["appid"] == "wx1234567890abcdef"
    assert frozen["notify_url"] == "https://merchant.example/pay/notify"
