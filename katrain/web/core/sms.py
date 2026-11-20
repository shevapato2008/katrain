"""The sole production SMS sender; credentials are loaded only on request."""

import hashlib
import hmac
import json
import logging
import re
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import httpx

from .phone import normalize_phone

_ENDPOINT = "https://dysmsapi.aliyuncs.com/"
_ALGORITHM = "ACS3-HMAC-SHA256"
_PRIVATE_HTTP = ContextVar("sms_private_http", default=False)


class _PrivateHttpFilter(logging.Filter):
    def filter(self, record):
        return not _PRIVATE_HTTP.get()


_HTTP_FILTER = _PrivateHttpFilter()


def _install_http_filter():
    # Logger filters are not inherited by child loggers. Cover httpcore's actual
    # transport loggers individually; the context flag leaves other tasks alone.
    names = {
        "httpx",
        "httpcore",
        "httpcore.connection",
        "httpcore.http11",
        "httpcore.http2",
        "httpcore.proxy",
        "httpcore.socks",
    }
    names.update(name for name in logging.Logger.manager.loggerDict if name.startswith("httpcore."))
    for name in names:
        logger = logging.getLogger(name)
        if _HTTP_FILTER not in logger.filters:
            logger.addFilter(_HTTP_FILTER)


def _signed_headers(headers):
    return {
        name.lower(): value.strip()
        for name, value in sorted(headers.items(), key=lambda item: item[0].lower())
        if name.lower() in {"host", "content-type"} or name.lower().startswith("x-acs-")
    }


def _canonical_request(headers, *, canonical_query=""):
    """Official ACS3 RPC canonical format; the SMS sender always has no query."""
    signed = _signed_headers(headers)
    canonical_headers = "".join(f"{name}:{value}\n" for name, value in signed.items())
    return "\n".join(
        ("POST", "/", canonical_query, canonical_headers, ";".join(signed), signed["x-acs-content-sha256"])
    )


def _authorization(headers, access_key_id, access_key_secret, *, canonical_query=""):
    canonical = _canonical_request(headers, canonical_query=canonical_query)
    string_to_sign = _ALGORITHM + "\n" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    signature = hmac.new(access_key_secret.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{_ALGORITHM} Credential={access_key_id},SignedHeaders={';'.join(_signed_headers(headers))},Signature={signature}"


# Only documented rejections are definitive. Unknown/new server error codes
# retain an unknown outcome so a possibly received code can still be verified.
_REJECTED_CODES = frozenset(
    {
        "isv.BUSINESS_LIMIT_CONTROL",
        "isv.MOBILE_NUMBER_ILLEGAL",
        "isv.AMOUNT_NOT_ENOUGH",
        "isv.OUT_OF_SERVICE",
        "isv.SMS_SIGNATURE_ILLEGAL",
        "isv.SMS_TEMPLATE_ILLEGAL",
        "isv.TEMPLATE_MISSING_PARAMETERS",
        "isv.PARAM_LENGTH_LIMIT",
        "isv.PARAM_NOT_SUPPORT_URL",
        "isv.SMS_CONTENT_ILLEGAL",
        "isv.BLACK_KEY_CONTROL_LIMIT",
        "isv.INVALID_PARAMETERS",
        "isv.INVALID_JSON_PARAM",
        "isv.SMS_SIGN_ILLEGAL",
        "isv.SMS_TEMPLATE_LIMIT",
        "isp.RAM_PERMISSION_DENY",
        "SignatureDoesNotMatch",
        "InvalidAccessKeyId.NotFound",
        "InvalidAccessKeyId",
        "Forbidden",
        "Forbidden.RAM",
        "MissingParameter",
        "InvalidParameter",
    }
)


class SmsUnavailable(Exception):
    def __init__(self):
        super().__init__("SMS is unavailable")


class SmsRejected(Exception):
    def __init__(self):
        super().__init__("SMS request was rejected")


class SmsUnknown(Exception):
    def __init__(self):
        super().__init__("SMS delivery status is unknown")


class AliyunSmsSender:
    def __init__(self, access_key_id, access_key_secret, sign_name, template_code, *, transport=None):
        values = (access_key_id, access_key_secret, sign_name, template_code)
        if any(
            not isinstance(value, str) or not value.strip() or any(ord(char) < 32 or ord(char) == 127 for char in value)
            for value in values
        ):
            raise SmsUnavailable()
        if any(
            not value.isascii() or any(char.isspace() for char in value)
            for value in (access_key_id, access_key_secret, template_code)
        ):
            raise SmsUnavailable()
        self._access_key_id = access_key_id
        self._access_key_secret = access_key_secret
        self._sign_name = sign_name
        self._template_code = template_code
        self._transport = transport

    async def send(self, phone_e164: str, code: str) -> None:
        """Submit once. Code=OK means accepted, never confirmed delivery."""
        valid_phone = False
        try:
            valid_phone = normalize_phone(phone_e164) == phone_e164
        except ValueError:
            pass
        if not valid_phone or not isinstance(code, str) or not re.fullmatch(r"[0-9]{6}", code):
            raise SmsRejected()

        body = urlencode(
            {
                "PhoneNumbers": phone_e164[3:],
                "SignName": self._sign_name,
                "TemplateCode": self._template_code,
                "TemplateParam": json.dumps({"code": code}, separators=(",", ":")),
            }
        ).encode("utf-8")
        headers = {
            "content-type": "application/x-www-form-urlencoded",
            "host": "dysmsapi.aliyuncs.com",
            "x-acs-action": "SendSms",
            "x-acs-version": "2017-05-25",
            "x-acs-date": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "x-acs-signature-nonce": uuid.uuid4().hex,
            "x-acs-content-sha256": hashlib.sha256(body).hexdigest(),
        }
        headers["authorization"] = _authorization(headers, self._access_key_id, self._access_key_secret)
        transport = self._transport if self._transport is not None else httpx.AsyncHTTPTransport(retries=0)
        _install_http_filter()
        token = _PRIVATE_HTTP.set(True)
        response = None
        try:
            async with httpx.AsyncClient(
                transport=transport, timeout=3.0, follow_redirects=False, trust_env=False
            ) as client:
                response = await client.post(_ENDPOINT, content=body, headers=headers)
        except httpx.HTTPError:
            pass
        finally:
            _PRIVATE_HTTP.reset(token)

        # Raise outside the except block: no original HTTP error context or
        # request/response object is attached to the safe public exception.
        if response is None or response.status_code >= 500 or 300 <= response.status_code < 400:
            raise SmsUnknown()
        payload = None
        try:
            payload = response.json()
        except (ValueError, UnicodeError):
            pass
        if not isinstance(payload, dict) or not isinstance(payload.get("Code"), str):
            raise SmsUnknown()
        if any(key in payload and not isinstance(payload[key], str) for key in ("RequestId", "Message", "BizId")):
            raise SmsUnknown()
        if payload["Code"] == "OK" and 200 <= response.status_code < 300:
            return
        if payload["Code"] in _REJECTED_CODES:
            raise SmsRejected()
        raise SmsUnknown()


def sender_from_settings(settings, *, transport=None):
    """Read an explicitly configured, read-only secret file; no env-key fallback."""
    path = getattr(settings, "KATRAIN_SMS_CREDENTIALS_FILE", "")
    sign_name = getattr(settings, "KATRAIN_SMS_SIGN_NAME", "")
    template_code = getattr(settings, "KATRAIN_SMS_TEMPLATE_CODE", "")
    if getattr(settings, "KATRAIN_SMS_ENABLED", False) is not True or not all((path, sign_name, template_code)):
        raise SmsUnavailable()

    credentials = {}
    failed = False
    try:
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            key, value = line.split("=", 1)
            if key in credentials:
                raise ValueError()
            credentials[key] = value.strip()
    except (OSError, UnicodeError, ValueError):
        failed = True
    expected = {"ALIBABA_CLOUD_ACCESS_KEY_ID", "ALIBABA_CLOUD_ACCESS_KEY_SECRET"}
    if failed or set(credentials) != expected or not all(credentials.values()):
        raise SmsUnavailable()
    return AliyunSmsSender(
        credentials["ALIBABA_CLOUD_ACCESS_KEY_ID"],
        credentials["ALIBABA_CLOUD_ACCESS_KEY_SECRET"],
        sign_name,
        template_code,
        transport=transport,
    )
