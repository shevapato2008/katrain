"""短信供应商抽象 + 生产 fail-fast。

这个文件里有两类断言，缺一不可：
  1. 闸函数本身对不对（直接调它）；
  2. 闸**真的接在生产唯一那条启动路径上**（读 `_lifespan_server` 的源码）。
第 2 类不是多余的 —— `tests/web_ui/test_secret_key_gate.py` 里写着本仓已经踩过
的那个坑：函数被测透，唯一的生产调用点没有闸，把那一行删掉整套测试不会红。
"""
import inspect as py_inspect

import httpx
import pytest

from katrain.web.core import config, sms
from katrain.web.core.config import KNOWN_SMS_PROVIDERS, assert_sms_provider_is_configured

# 阿里云 RPC 签名机制文档里的示例向量。**照抄文档，不是我们自己算的**：
# 拿它钉死 string-to-sign 与最终签名，才挡得住"签名算错"——那种错的表现是
# 运营商侧 SignatureDoesNotMatch，一个我们在自己日志里解释不了的失败。
_DOC_PARAMS = {
    # 顺序**故意不按字典序**：签名要求先 sorted()，这样排列本身就在检验它。
    "Format": "XML",
    "Version": "2014-05-26",
    "AccessKeyId": "testid",
    "SignatureMethod": "HMAC-SHA1",
    "Timestamp": "2016-02-23T12:46:24Z",
    "SignatureVersion": "1.0",
    "SignatureNonce": "3ee8c1b8-83d3-44af-a94f-4e0ad82fd6cf",
    "Action": "DescribeRegions",
}
_DOC_STRING_TO_SIGN = (
    "GET&%2F&AccessKeyId%3Dtestid%26Action%3DDescribeRegions%26Format%3DXML"
    "%26SignatureMethod%3DHMAC-SHA1"
    "%26SignatureNonce%3D3ee8c1b8-83d3-44af-a94f-4e0ad82fd6cf"
    "%26SignatureVersion%3D1.0%26Timestamp%3D2016-02-23T12%253A46%253A24Z"
    "%26Version%3D2014-05-26"
)
_DOC_SIGNATURE = "OLeaidS1JvxuMvnyHOwuJ+uX5qY="


def _doc_provider(transport=None):
    return sms.AliyunProvider(
        access_key_id="testid",
        access_key_secret="testsecret",
        sign_name="万智星",
        template_code="SMS_1",
        transport=transport,
    )


# --- 闸函数本身 -------------------------------------------------------------

def test_server_mode_refuses_to_start_without_a_provider():
    """生产未显式配置就 fail-fast。**console 不许在生产静默生效** ——
    那会让 send-code 一路返回 200 而用户永远收不到码（spec §2.1）。"""
    with pytest.raises(RuntimeError, match="KATRAIN_SMS_PROVIDER"):
        assert_sms_provider_is_configured("server", "")


def test_server_mode_refuses_the_console_provider():
    with pytest.raises(RuntimeError, match="console"):
        assert_sms_provider_is_configured("server", "console")


def test_console_is_allowed_only_with_the_explicit_opt_in():
    """默认关 ⇒ 拒；显式打开 ⇒ 放行。本机真浏览器验收靠这条，生产两台机器都不设。"""
    assert assert_sms_provider_is_configured("server", "console", allow_console=True) is None


def test_the_opt_in_does_not_rescue_an_empty_or_unknown_provider():
    """放行口只对 console 开，不是"配错也能起"的万能开关。"""
    for bad in ("", "aliyu"):
        with pytest.raises(RuntimeError):
            assert_sms_provider_is_configured("server", bad, allow_console=True)


def test_server_mode_refuses_an_unknown_provider_name():
    """`KATRAIN_SMS_PROVIDER=aliyu` 这种手滑今天能正常启动，直到第一个用户
    点"发送验证码"才在 get_provider() 里炸 —— 启动期判得了的事不留到请求期。"""
    with pytest.raises(RuntimeError, match="未知的 SMS_PROVIDER"):
        assert_sms_provider_is_configured("server", "aliyu")


def test_server_mode_accepts_aliyun():
    assert assert_sms_provider_is_configured("server", "aliyun") is None


def test_board_mode_is_allowed_without_a_provider():
    """盒子不发短信（四个端点在盒子上 403/503），不该因此拒绝启动。"""
    assert assert_sms_provider_is_configured("board", "") is None


def test_every_known_provider_name_can_actually_be_constructed(monkeypatch):
    """闸放行的名字，工厂必须造得出来。

    两份名单各写各的时，"闸放行了一个工厂造不出来的名字"这种配置会一路活到
    第一个用户点发送。KNOWN_SMS_PROVIDERS 是唯一真源，这条测试是它的绑定。
    """
    for name in KNOWN_SMS_PROVIDERS:
        monkeypatch.setattr(config.settings, "SMS_PROVIDER", name)
        assert isinstance(sms.get_provider(), sms.SmsProvider), name


def test_sms_settings_are_wired_to_env_not_only_declared(monkeypatch):
    """字段声明了但 `Settings.__init__` 里没装配 ⇒ 线上设了 env 也不生效，
    表现是"限流参数怎么调都不动"这种没有任何报错的故障。两处都要写。"""
    monkeypatch.setenv("KATRAIN_SMS_PROVIDER", "aliyun")
    monkeypatch.setenv("KATRAIN_SMS_DAILY_CAP_INTL", "7")
    monkeypatch.setenv("KATRAIN_SMS_COOLDOWN_SEC", "11")
    fresh = config.Settings()
    assert fresh.SMS_PROVIDER == "aliyun"
    assert fresh.SMS_DAILY_CAP_INTL == 7
    assert fresh.SMS_COOLDOWN_SEC == 11


# --- 两个提供方 -------------------------------------------------------------

@pytest.mark.asyncio
async def test_console_provider_prints_a_masked_number_and_the_code(capsys):
    p = sms.ConsoleProvider()
    await p.send("+8613800138000", "123456", is_intl=False)
    out = capsys.readouterr().out
    assert "+86 138****8000" in out     # 掩码，不打明文号
    assert "+8613800138000" not in out
    assert "123456" in out              # 开发要看得到码


def test_aliyun_picks_endpoint_and_action_by_region():
    p = _doc_provider()
    assert p._endpoint(is_intl=False) == "https://dysmsapi.aliyuncs.com/"
    assert p._endpoint(is_intl=True) == "https://dysmsapi.ap-southeast-1.aliyuncs.com/"
    assert p._action(is_intl=False) == "SendSms"
    assert p._action(is_intl=True) == "SendMessageToGlobe"


def test_aliyun_string_to_sign_matches_the_documented_example():
    """把中间产物钉死。

    只断言 `len(sig) == 28` 是假绿：**任何** base64(HMAC-SHA1) 都是 28 字符；
    只断言"与字典顺序无关"也是假绿：任何做了 sorted() 的实现都满足它。
    两条都对一个拼错的 string-to-sign 免疫。
    """
    assert _doc_provider()._string_to_sign(_DOC_PARAMS) == _DOC_STRING_TO_SIGN


def test_aliyun_signature_matches_the_documented_example():
    """HMAC 密钥是 secret + 尾随 `&`。少了那个 `&` 得到的是
    `R8VkbeU3DqhHmAVCdxW/CjqsRK0=` —— 同样 28 字符、同样与顺序无关。"""
    assert _doc_provider()._sign(_DOC_PARAMS) == _DOC_SIGNATURE


# --- send() 的三条出口 ------------------------------------------------------

@pytest.mark.asyncio
async def test_aliyun_domestic_send_signs_and_succeeds_when_code_is_ok():
    seen = {}

    def handler(request):
        seen.update(dict(request.url.params))
        return httpx.Response(200, json={"Code": "OK", "Message": "OK"})

    p = _doc_provider(transport=httpx.MockTransport(handler))
    assert await p.send("+8613800138000", "123456", is_intl=False) is None
    assert seen["Action"] == "SendSms"
    assert seen["PhoneNumbers"] == "13800138000"     # 国内通道**不带** +86
    assert seen["SignName"] == "万智星"
    assert seen["TemplateCode"] == "SMS_1"
    assert "123456" in seen["TemplateParam"]
    assert seen["Signature"]                          # 请求里真的带了签名


@pytest.mark.asyncio
async def test_aliyun_intl_send_uses_the_global_action_and_full_e164():
    """国际通道不需要签名与模板报备 ⇒ 它是最先能端到端跑通的那条（D-U4）。"""
    seen = {}

    def handler(request):
        seen.update(dict(request.url.params))
        return httpx.Response(200, json={"Code": "OK"})

    p = _doc_provider(transport=httpx.MockTransport(handler))
    await p.send("+85298765432", "654321", is_intl=True)
    assert seen["Action"] == "SendMessageToGlobe"
    assert seen["To"] == "+85298765432"
    assert "654321" in seen["Message"]


@pytest.mark.asyncio
async def test_aliyun_code_not_ok_raises_sms_rejected():
    """HTTP 200 但 Code != OK = **明确拒收，确定没计费**。

    合成一类的后果：send-code 不鉴权，攻击者拿格式合法但一定被拒的号
    零成本把全站日额度打满，当天所有人拿不到码，而我们一分钱短信费都没花。
    """
    def handler(request):
        return httpx.Response(200, json={"Code": "isv.MOBILE_NUMBER_ILLEGAL", "Message": "bad"})

    p = _doc_provider(transport=httpx.MockTransport(handler))
    with pytest.raises(sms.SmsRejected):
        await p.send("+9991234567", "123456", is_intl=True)


@pytest.mark.asyncio
async def test_aliyun_5xx_raises_sms_unreachable():
    """5xx 时我们**不知道**它收没收 ⇒ 保守计入日额度。"""
    def handler(request):
        return httpx.Response(503, text="upstream down")

    p = _doc_provider(transport=httpx.MockTransport(handler))
    with pytest.raises(sms.SmsUnreachable):
        await p.send("+8613800138000", "123456", is_intl=False)


@pytest.mark.asyncio
async def test_aliyun_timeout_raises_sms_unreachable():
    def handler(request):
        raise httpx.ConnectTimeout("simulated")

    p = _doc_provider(transport=httpx.MockTransport(handler))
    with pytest.raises(sms.SmsUnreachable):
        await p.send("+8613800138000", "123456", is_intl=False)


def test_rejected_is_not_swallowed_by_except_unreachable():
    """两个类必须是**兄弟**，不是父子。

    把 SmsRejected 写成 SmsUnreachable 的子类，Task 6 里 `except SmsUnreachable`
    就会把拒收也当成不可达 —— 拒收重新开始占日额度，而且没有任何报错。
    """
    assert issubclass(sms.SmsRejected, sms.SmsProviderError)
    assert issubclass(sms.SmsUnreachable, sms.SmsProviderError)
    assert not issubclass(sms.SmsRejected, sms.SmsUnreachable)
    assert not issubclass(sms.SmsUnreachable, sms.SmsRejected)


# --- 闸必须在生产唯一的启动路径上 -------------------------------------------
#
# 上面那些直接调 assert_sms_provider_is_configured()，把**函数**测透了；
# 它在生产的唯一调用者是 server._lifespan_server。照抄
# tests/web_ui/test_secret_key_gate.py 里那两条的形状。
# 区别一处：那边搜的是**裸函数名**，会连 `from … import …` 那一行一起命中 ——
# 于是"只删调用、留着 import"这种改法它看不见。这里搜**带左括号**的形式。

def test_sms_gate_is_wired_into_the_server_lifespan():
    """删掉 server.py 里那一行调用，这条必须红。"""
    from katrain.web import server

    src = py_inspect.getsource(server._lifespan_server)
    assert "assert_sms_provider_is_configured(" in src, (
        "服务端 lifespan 里没有 SMS_PROVIDER 闸 —— 闸函数写得再好，没人调就是摆设"
    )


def test_sms_gate_runs_before_any_database_work():
    """闸必须挡在任何 DB 动作之前，否则一个配错的部署会先把 engine/router 拉起来、
    可能已经写了库，再拒绝启动 —— 那不是 fail-fast。"""
    from katrain.web import server

    lines = py_inspect.getsource(server._lifespan_server).splitlines()
    gate_at = next(
        (i for i, l in enumerate(lines) if "assert_sms_provider_is_configured(" in l), None
    )
    assert gate_at is not None, "lifespan 里根本没有这个调用"
    db_markers = ("init_db", "SessionLocal", "create_engine", "session_factory")
    first_db = next(
        (i for i, l in enumerate(lines) if any(m in l for m in db_markers)), len(lines)
    )
    assert gate_at < first_db, (
        f"闸在第 {gate_at} 行，而第一处 DB 动作在第 {first_db} 行 —— 闸必须在前面"
    )
