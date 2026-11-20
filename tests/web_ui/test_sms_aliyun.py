"""No live SMS credentials, database, or transport are used by these tests."""

import hashlib
import json
import logging
import tempfile
import traceback
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs

import httpx
import pytest

from katrain.web.core.sms import AliyunSmsSender, SmsRejected, SmsUnavailable, SmsUnknown, sender_from_settings


def settings(**overrides):
    values = dict(
        KATRAIN_SMS_ENABLED=True,
        KATRAIN_SMS_CREDENTIALS_FILE="",
        KATRAIN_SMS_SIGN_NAME="北京万智星科技",
        KATRAIN_SMS_TEMPLATE_CODE="SMS_512325758",
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def test_unavailable_configuration_does_not_load_credentials(monkeypatch):
    def forbidden_read(*args, **kwargs):
        pytest.fail("disabled or incomplete configuration must not read credentials")

    monkeypatch.setattr("pathlib.Path.read_text", forbidden_read)
    for value in (settings(KATRAIN_SMS_ENABLED=False), settings(), settings(KATRAIN_SMS_SIGN_NAME="")):
        with pytest.raises(SmsUnavailable, match="^SMS is unavailable$"):
            sender_from_settings(value)


@pytest.fixture
def fake_credentials_path():
    with tempfile.TemporaryDirectory(prefix="katrain-sms-test-", dir="/tmp") as directory:
        yield Path(directory) / "fake-sms.env"


def test_factory_reads_only_explicit_fake_file_and_never_environment_keys(fake_credentials_path, monkeypatch):
    path = fake_credentials_path
    path.write_text("ALIBABA_CLOUD_ACCESS_KEY_ID=fake-key-id\nALIBABA_CLOUD_ACCESS_KEY_SECRET=fake-key-secret\n")
    monkeypatch.setenv("ALIBABA_CLOUD_ACCESS_KEY_ID", "env-key-must-not-be-used")
    monkeypatch.setenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET", "env-secret-must-not-be-used")
    sender = sender_from_settings(settings(KATRAIN_SMS_CREDENTIALS_FILE=str(path)))
    assert isinstance(sender, AliyunSmsSender)
    assert "fake-key" not in repr(sender)
    with pytest.raises(SmsUnavailable):
        sender_from_settings(settings(KATRAIN_SMS_CREDENTIALS_FILE=str(path.parent / "missing")))


def test_exception_strings_are_safe_constants():
    assert str(SmsUnavailable()) == "SMS is unavailable"
    assert str(SmsRejected()) == "SMS request was rejected"
    assert str(SmsUnknown()) == "SMS delivery status is unknown"


def test_official_acs3_canonical_request_and_signature_vector():
    # Official fixed example, not a signature recalculated from our implementation:
    # https://help.aliyun.com/zh/sdk/product-overview/v3-request-structure-and-signature
    from katrain.web.core.sms import _authorization, _canonical_request

    headers = {
        "host": "ecs.cn-shanghai.aliyuncs.com",
        "x-acs-action": "RunInstances",
        "x-acs-content-sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "x-acs-date": "2023-10-26T10:22:32Z",
        "x-acs-signature-nonce": "3156853299f313e23d1673dc12e1703d",
        "x-acs-version": "2014-05-26",
    }
    query = "ImageId=win2019_1809_x64_dtc_zh-cn_40G_alibase_20230811.vhd&RegionId=cn-shanghai"
    signed = "host;x-acs-action;x-acs-content-sha256;x-acs-date;x-acs-signature-nonce;x-acs-version"
    expected = (
        "POST\n/\n" + query + "\n"
        "host:ecs.cn-shanghai.aliyuncs.com\n"
        "x-acs-action:RunInstances\n"
        "x-acs-content-sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855\n"
        "x-acs-date:2023-10-26T10:22:32Z\n"
        "x-acs-signature-nonce:3156853299f313e23d1673dc12e1703d\n"
        "x-acs-version:2014-05-26\n\n" + signed + "\n"
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )
    canonical = _canonical_request(headers, canonical_query=query)
    assert canonical == expected
    assert (
        hashlib.sha256(canonical.encode()).hexdigest()
        == "7ea06492da5221eba5297e897ce16e55f964061054b7695beedaac1145b1e259"
    )
    assert _authorization(headers, "YourAccessKeyId", "YourAccessKeySecret", canonical_query=query) == (
        "ACS3-HMAC-SHA256 Credential=YourAccessKeyId,SignedHeaders="
        + signed
        + ",Signature=06563a9e1b43f5dfe96b81484da74bceab24a1d853912eee15083a6f0f3283c0"
    )


@pytest.mark.asyncio
async def test_send_is_one_domestic_post_with_private_form_body():
    requests = []

    def handle(request):
        requests.append(request)
        assert request.method == "POST"
        assert str(request.url) == "https://dysmsapi.aliyuncs.com/"
        assert request.url.query == b""
        assert request.headers["x-acs-action"] == "SendSms"
        assert request.headers["x-acs-version"] == "2017-05-25"
        assert request.headers["content-type"] == "application/x-www-form-urlencoded"
        assert request.headers["x-acs-content-sha256"] == hashlib.sha256(request.content).hexdigest()
        assert "SignedHeaders=content-type;host;x-acs-action;" in request.headers["authorization"]
        assert request.extensions["timeout"] == {"connect": 3.0, "read": 3.0, "write": 3.0, "pool": 3.0}
        form = parse_qs(request.content.decode(), strict_parsing=True)
        assert form == {
            "PhoneNumbers": ["13800138000"],
            "SignName": ["北京万智星科技"],
            "TemplateCode": ["SMS_512325758"],
            "TemplateParam": ['{"code":"926481"}'],
        }
        assert json.loads(form["TemplateParam"][0]) == {"code": "926481"}
        return httpx.Response(200, json={"Code": "OK", "Message": "OK", "RequestId": "safe-request-id"})

    sender = AliyunSmsSender(
        "fake-key-id", "fake-key-secret", "北京万智星科技", "SMS_512325758", transport=httpx.MockTransport(handle)
    )
    assert await sender.send("+8613800138000", "926481") is None
    assert len(requests) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "phone,code",
    [
        ("13800138000", "926481"),
        ("+85213800138000", "926481"),
        ("+8613800138000,+8613900139000", "926481"),
        ("+861３800138000", "926481"),
        ("+8613800138000", "１２３４５６"),
        ("+8613800138000", "12345"),
        ("+8613800138000", 123456),
    ],
)
async def test_invalid_send_input_never_reaches_transport(phone, code):
    def forbidden(request):
        pytest.fail("invalid input must not reach the network")

    sender = AliyunSmsSender("fake-id", "fake-secret", "sign", "template", transport=httpx.MockTransport(forbidden))
    with pytest.raises(SmsRejected):
        await sender.send(phone, code)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,payload,error",
    [
        (200, {"Code": "isv.BUSINESS_LIMIT_CONTROL", "Message": "not safe"}, SmsRejected),
        (400, {"Code": "isv.MOBILE_NUMBER_ILLEGAL"}, SmsRejected),
        (200, {"Code": "SignatureDoesNotMatch"}, SmsRejected),
        (200, {"Code": "isv.SYSTEM_ERROR"}, SmsUnknown),
        (200, {"Code": "InternalError"}, SmsUnknown),
        (200, {"Code": "UnexpectedProviderValue"}, SmsUnknown),
        (500, {"Code": "isv.BUSINESS_LIMIT_CONTROL"}, SmsUnknown),
        (503, {"Code": "OK"}, SmsUnknown),
        (302, {"Code": "OK"}, SmsUnknown),
        (200, None, SmsUnknown),
        (200, [], SmsUnknown),
        (200, {}, SmsUnknown),
        (200, {"Code": 1}, SmsUnknown),
        (200, {"Code": ""}, SmsUnknown),
        (200, {"Code": "OK", "RequestId": []}, SmsUnknown),
        (400, {"Code": "OK"}, SmsUnknown),
    ],
)
async def test_provider_result_classification_has_no_retry(status, payload, error):
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(status, json=payload, headers={"location": "https://unexpected.invalid/"})

    sender = AliyunSmsSender("fake-id", "fake-secret", "sign", "template", transport=httpx.MockTransport(handle))
    with pytest.raises(error):
        await sender.send("+8613800138000", "926481")
    assert len(requests) == 1


@pytest.mark.asyncio
async def test_bad_json_and_timeout_have_safe_errors_and_http_logs(caplog):
    sensitive = "13800138000 926481 fake-key-id fake-key-secret"
    phone, code, key_id, key_secret = sensitive.split()
    phone = "+86" + phone
    caplog.set_level(logging.DEBUG)
    for timeout in (False, True):
        calls = []

        def handle(request):
            calls.append(request)
            for name in ("httpx", "httpcore.connection", "httpcore.http11", "httpcore.http2", "httpcore.proxy"):
                logging.getLogger(name).debug("private request %s %r %s", sensitive, request.headers, request.content)
            if timeout:
                raise httpx.ReadTimeout(sensitive, request=request)
            return httpx.Response(200, content=sensitive.encode())

        sender = AliyunSmsSender(key_id, key_secret, "sign", "template", transport=httpx.MockTransport(handle))
        with pytest.raises(SmsUnknown) as caught:
            await sender.send(phone, code)
        assert caught.value.__context__ is None
        diagnostic = "".join(traceback.format_exception(caught.value)) + caplog.text
        for secret in sensitive.split():
            assert secret not in diagnostic
        assert len(calls) == 1
    logging.getLogger("httpx").debug("unrelated request remains observable")
    assert "unrelated request remains observable" in caplog.text


@pytest.mark.parametrize(
    "content",
    [
        "ALIBABA_CLOUD_ACCESS_KEY_ID=fake-only-id\n",
        "ALIBABA_CLOUD_ACCESS_KEY_ID=fake-id\nALIBABA_CLOUD_ACCESS_KEY_SECRET=\n",
        "ALIBABA_CLOUD_ACCESS_KEY_ID=fake-id\nALIBABA_CLOUD_ACCESS_KEY_SECRET=fake-secret\nEXTRA=unexpected\n",
        "ALIBABA_CLOUD_ACCESS_KEY_ID=fake-id\nALIBABA_CLOUD_ACCESS_KEY_ID=duplicate\nALIBABA_CLOUD_ACCESS_KEY_SECRET=fake-secret\n",
        "not-a-credentials-file",
        "ALIBABA_CLOUD_ACCESS_KEY_ID=fake id\nALIBABA_CLOUD_ACCESS_KEY_SECRET=fake-secret\n",
    ],
)
def test_malformed_fake_credentials_are_safely_unavailable(fake_credentials_path, content):
    fake_credentials_path.write_text(content)
    with pytest.raises(SmsUnavailable) as caught:
        sender_from_settings(settings(KATRAIN_SMS_CREDENTIALS_FILE=str(fake_credentials_path)))
    assert caught.value.__context__ is None
    assert str(fake_credentials_path) not in str(caught.value)
    assert content not in repr(caught.value)


@pytest.mark.parametrize("value", ["", " ", None, "unsafe\nvalue"])
def test_constructor_rejects_missing_or_malformed_configuration(value):
    with pytest.raises(SmsUnavailable):
        AliyunSmsSender(value, "fake-secret", "sign", "template")
    with pytest.raises(SmsUnavailable):
        AliyunSmsSender("fake-id", "fake-secret", value, "template")
