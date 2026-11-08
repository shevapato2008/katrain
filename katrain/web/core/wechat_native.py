"""WeChat Pay Native API v3 protocol boundary (no database or billing state).

Only configured WeChat Pay public-key IDs are trusted. Merchant-platform callback
migration to public-key mode must be completed before enabling live payments;
unknown certificate serials are deliberately rejected rather than bypassed.
"""

import base64
import binascii
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
import json
from pathlib import Path
import re
import secrets
import time
from typing import Any
from urllib.parse import quote, urlencode, urlsplit

import httpx
from cryptography.exceptions import InvalidSignature, InvalidTag, UnsupportedAlgorithm
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


API_ORIGIN = "https://api.mch.weixin.qq.com"
MAX_BODY_BYTES = 64 * 1024
MAX_CLOCK_SKEW_SECONDS = 300
REQUEST_BUDGET_SECONDS = 10
_ORDER_PATTERN = r"[A-Za-z0-9_|*\-]{6,32}"
_CONFIG_FIELDS = (
    "APP_ID",
    "MCH_ID",
    "MERCHANT_SERIAL",
    "PRIVATE_KEY_PATH",
    "API_V3_KEY_PATH",
    "PUBLIC_KEY_ID",
    "PUBLIC_KEY_PATH",
    "NOTIFY_URL",
)
_SIGNATURE_HEADERS = ("wechatpay-timestamp", "wechatpay-nonce", "wechatpay-signature", "wechatpay-serial")


class WechatNativeError(Exception):
    """A stable local error code; upstream body, headers and secrets stay private."""

    def __init__(self, code: str, *, status_code: int | None = None):
        self.code = code
        self.status_code = status_code
        super().__init__(code)


class WechatConfigurationError(WechatNativeError):
    def __init__(self):
        super().__init__("configuration_invalid")


def _matches(value: Any, pattern: str) -> bool:
    return isinstance(value, str) and re.fullmatch(pattern, value, flags=re.ASCII) is not None


def _https_notify_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
        return (
            1 <= len(value) <= 256
            and value.isascii()
            and not any(c.isspace() for c in value)
            and parsed.scheme == "https"
            and bool(parsed.hostname)
            and bool(parsed.path)
            and not parsed.username
            and not parsed.password
            and not parsed.query
            and not parsed.fragment
            and parsed.port in (None, 443)
        )
    except (TypeError, ValueError):
        return False


@dataclass(frozen=True)
class WechatNativeConfig:
    app_id: str
    mch_id: str
    merchant_serial: str
    public_key_id: str
    notify_url: str
    private_key: rsa.RSAPrivateKey = field(repr=False, compare=False)
    public_key: rsa.RSAPublicKey = field(repr=False, compare=False)
    api_v3_key: bytes = field(repr=False)

    @classmethod
    def from_settings(cls, settings: Any) -> "WechatNativeConfig":
        try:
            values = tuple(getattr(settings, f"WECHAT_PAY_{name}", "") for name in _CONFIG_FIELDS)
            if not all(isinstance(value, str) and value for value in values):
                raise ValueError
            app_id, mch_id, serial, private_path, api_path, public_id, public_path, notify = values
            if not (
                _matches(app_id, r"[A-Za-z0-9]{1,32}")
                and _matches(mch_id, r"[0-9]{1,32}")
                and _matches(serial, r"[A-Fa-f0-9]{1,64}")
                and _matches(public_id, r"PUB_KEY_ID_[A-Za-z0-9_]{1,100}")
                and _https_notify_url(notify)
            ):
                raise ValueError
            # Stat before lookup: replacing/rewriting a file reloads it, while catalog
            # polling does not repeatedly parse and validate three cryptographic keys.
            versions = []
            for file_path in (private_path, api_path, public_path):
                path = Path(file_path)
                stat = path.stat()
                if not path.is_file() or stat.st_size > 16 * 1024:
                    raise ValueError
                versions.append((stat.st_dev, stat.st_ino, stat.st_mtime_ns, stat.st_size))
            return _load_config(values, tuple(versions))
        except (OSError, ValueError, TypeError, UnsupportedAlgorithm):
            raise WechatConfigurationError() from None


@lru_cache(maxsize=8)
def _load_config(values: tuple[str, ...], versions: tuple) -> WechatNativeConfig:
    app_id, mch_id, serial, private_path, api_path, public_id, public_path, notify = values

    def read_key(path):
        with open(path, "rb") as stream:
            data = stream.read(16 * 1024 + 1)
        if len(data) > 16 * 1024:
            raise ValueError
        return data

    private = serialization.load_pem_private_key(read_key(private_path), password=None)
    public = serialization.load_pem_public_key(read_key(public_path))
    api_key = read_key(api_path)
    if not (
        isinstance(private, rsa.RSAPrivateKey)
        and private.key_size == 2048
        and isinstance(public, rsa.RSAPublicKey)
        and public.key_size == 2048
        and len(api_key) == 32
    ):
        raise ValueError
    return WechatNativeConfig(app_id, mch_id, serial, public_id, notify, private, public, api_key)


def wechat_native_ready(settings: Any) -> bool:
    """Credentials ready, independently of the new-payment switch.

    Existing orders still need authenticated reconciliation after live is disabled.
    This does not attest to the merchant platform's separate migration/permissions.
    """
    try:
        WechatNativeConfig.from_settings(settings)
        return True
    except WechatConfigurationError:
        return False


def _json_object(raw: bytes) -> dict:
    try:
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError
        return value
    except (ValueError, UnicodeError, RecursionError):
        raise WechatNativeError("invalid_payload") from None


class WechatNativeClient:
    def __init__(self, config: WechatNativeConfig, *, transport=None, clock: Callable[[], float] = time.time):
        self.config = config
        self._transport = transport
        self._clock = clock

    @classmethod
    def from_settings(cls, settings: Any, *, transport=None, clock: Callable[[], float] = time.time):
        return cls(WechatNativeConfig.from_settings(settings), transport=transport, clock=clock)

    def readiness(self) -> bool:
        return True  # construction already validated the immutable configuration

    def _verify(self, headers: Mapping[str, str], raw: bytes) -> None:
        headers = {key.lower(): value for key, value in headers.items()}
        stamp, nonce, signature, serial = (headers.get(key, "") for key in _SIGNATURE_HEADERS)
        try:
            if not (
                _matches(stamp, r"[0-9]{1,12}")
                and abs(self._clock() - int(stamp)) <= MAX_CLOCK_SKEW_SECONDS
                and _matches(nonce, r"[!-~]{1,256}")
                and isinstance(signature, str)
                and len(signature) <= 512
                and serial == self.config.public_key_id
            ):
                raise ValueError
            signature_bytes = base64.b64decode(signature, validate=True)
            canonical = stamp.encode("ascii") + b"\n" + nonce.encode("ascii") + b"\n" + raw + b"\n"
            self.config.public_key.verify(signature_bytes, canonical, padding.PKCS1v15(), hashes.SHA256())
        except (ValueError, TypeError, UnicodeError, binascii.Error, InvalidSignature):
            raise WechatNativeError("invalid_signature") from None

    def _request(self, method: str, path: str, payload: Mapping | None = None, *, expected_status: int) -> bytes:
        started = time.monotonic()
        raw = (
            b""
            if payload is None
            else json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
        )
        if len(raw) > MAX_BODY_BYTES:
            raise WechatNativeError("invalid_payload")
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "identity",
            "User-Agent": "KaTrain-WechatNative/1",
            "Wechatpay-Serial": self.config.public_key_id,
        }
        if payload is not None:
            headers["Content-Type"] = "application/json"
        try:
            with httpx.Client(
                transport=self._transport,
                verify=True,
                follow_redirects=False,
                trust_env=False,
                timeout=httpx.Timeout(5.0, connect=3.0),
            ) as client:
                request = client.build_request(method, API_ORIGIN + path, content=raw, headers=headers)
                stamp, nonce = str(int(self._clock())), secrets.token_hex(16)
                canonical = (
                    method.encode("ascii")
                    + b"\n"
                    + request.url.raw_path
                    + b"\n"
                    + stamp.encode("ascii")
                    + b"\n"
                    + nonce.encode("ascii")
                    + b"\n"
                    + raw
                    + b"\n"
                )
                signature = base64.b64encode(
                    self.config.private_key.sign(canonical, padding.PKCS1v15(), hashes.SHA256())
                ).decode("ascii")
                request.headers["Authorization"] = (
                    f'WECHATPAY2-SHA256-RSA2048 mchid="{self.config.mch_id}",nonce_str="{nonce}",'
                    f'timestamp="{stamp}",serial_no="{self.config.merchant_serial}",signature="{signature}"'
                )
                response = client.send(request, stream=True)
                try:
                    if time.monotonic() - started > REQUEST_BUDGET_SECONDS:
                        raise WechatNativeError("transport_error")
                    if response.headers.get("content-encoding", "identity").lower() != "identity":
                        raise WechatNativeError("invalid_payload")
                    chunks, size = [], 0
                    # MockTransport may provide a pre-buffered response; real HTTP uses raw streaming.
                    iterator = (response.content,) if response.is_stream_consumed else response.iter_raw()
                    for chunk in iterator:
                        # A read may overshoot the total budget by at most its 5s
                        # phase timeout; a slow drip must not keep an order lease alive.
                        if time.monotonic() - started > REQUEST_BUDGET_SECONDS:
                            raise WechatNativeError("transport_error")
                        size += len(chunk)
                        if size > MAX_BODY_BYTES:
                            raise WechatNativeError("invalid_payload")
                        chunks.append(chunk)
                    body = b"".join(chunks)
                    if 200 <= response.status_code < 300:
                        self._verify(response.headers, body)
                        if response.status_code != expected_status:
                            raise WechatNativeError("invalid_payload")
                        return body
                    if any(name in response.headers for name in _SIGNATURE_HEADERS):
                        self._verify(response.headers, body)
                    # Even a verified provider error is not proof that an order is closed/unpaid.
                    raise WechatNativeError("provider_error", status_code=response.status_code)
                finally:
                    response.close()
        except httpx.HTTPError:
            raise WechatNativeError("transport_error") from None

    def create_native(self, request: Mapping[str, Any]) -> str:
        try:
            amount = request.get("amount", {})
            expiry = request.get("time_expire", "")
            if not (
                _matches(request.get("appid"), r"[A-Za-z0-9]{1,32}")
                and request.get("mchid") == self.config.mch_id
                and _https_notify_url(request.get("notify_url"))
                and _matches(request.get("out_trade_no"), _ORDER_PATTERN)
                and isinstance(request.get("description"), str)
                and 1 <= len(request["description"].encode()) <= 127
                and isinstance(amount, Mapping)
                and type(amount.get("total")) is int
                and 0 < amount["total"] <= 2**31 - 1
                and amount.get("currency") == "CNY"
                and _matches(
                    expiry,
                    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
                    r"(?:\.[0-9]{1,9})?(?:Z|[+\-][0-9]{2}:[0-9]{2})",
                )
                and datetime.fromisoformat(expiry.replace("Z", "+00:00")).utcoffset() is not None
                and set(request)
                <= {"appid", "mchid", "description", "out_trade_no", "notify_url", "amount", "time_expire", "attach"}
                and (
                    "attach" not in request
                    or isinstance(request["attach"], str)
                    and len(request["attach"].encode()) <= 128
                )
            ):
                raise ValueError
            # The order service freezes AppID/callback on creation. Same-merchant
            # recovery must retain those fields after runtime configuration changes.
            # Serialize a snapshot once; never edit/replace the caller's frozen fields.
            snapshot = _json_object(json.dumps(dict(request), ensure_ascii=False, allow_nan=False).encode())
        except (ValueError, TypeError, AttributeError, UnicodeError):
            raise WechatNativeError("invalid_payload") from None
        data = _json_object(self._request("POST", "/v3/pay/transactions/native", snapshot, expected_status=200))
        code_url = data.get("code_url")
        try:
            # Official examples use different hosts and paths, including /up.
            # Authentication establishes the source; preserve the QR payload exactly.
            if not (_matches(code_url, r"weixin://[!-~]{1,2039}") and urlsplit(code_url).netloc):
                raise ValueError
        except ValueError:
            raise WechatNativeError("invalid_payload") from None
        return code_url

    def query(self, out_trade_no: str) -> dict:
        if not _matches(out_trade_no, _ORDER_PATTERN):
            raise WechatNativeError("invalid_payload")
        path = "/v3/pay/transactions/out-trade-no/" + quote(out_trade_no, safe="")
        path += "?" + urlencode({"mchid": self.config.mch_id})
        return _json_object(self._request("GET", path, expected_status=200))

    def close(self, out_trade_no: str) -> None:
        if not _matches(out_trade_no, _ORDER_PATTERN):
            raise WechatNativeError("invalid_payload")
        path = "/v3/pay/transactions/out-trade-no/" + quote(out_trade_no, safe="") + "/close"
        body = self._request("POST", path, {"mchid": self.config.mch_id}, expected_status=204)
        if body:
            raise WechatNativeError("invalid_payload")

    def decode_notification(self, headers: Mapping[str, str], raw_body: bytes) -> dict:
        if not isinstance(raw_body, bytes) or len(raw_body) > MAX_BODY_BYTES:
            raise WechatNativeError("invalid_payload")
        self._verify(headers, raw_body)
        envelope = _json_object(raw_body)
        try:
            resource = envelope.get("resource", {})
            if not (
                isinstance(envelope.get("id"), str)
                and 1 <= len(envelope["id"]) <= 128
                and envelope.get("event_type") == "TRANSACTION.SUCCESS"
                and envelope.get("resource_type") == "encrypt-resource"
                and isinstance(resource, dict)
                and resource.get("original_type") == "transaction"
                and resource.get("algorithm") == "AEAD_AES_256_GCM"
                and isinstance(resource.get("nonce"), str)
                and len(resource["nonce"].encode("utf-8")) == 12
                and isinstance(resource.get("associated_data", ""), str)
                and len(resource.get("associated_data", "").encode("utf-8")) <= 128
                and isinstance(resource.get("ciphertext"), str)
                and len(resource["ciphertext"]) <= MAX_BODY_BYTES
            ):
                raise ValueError
            encrypted = base64.b64decode(resource["ciphertext"], validate=True)
            decrypted = AESGCM(self.config.api_v3_key).decrypt(
                resource["nonce"].encode(), encrypted, resource.get("associated_data", "").encode()
            )
            return _json_object(decrypted)
        except (ValueError, TypeError, UnicodeError, binascii.Error, InvalidTag):
            raise WechatNativeError("invalid_payload") from None
