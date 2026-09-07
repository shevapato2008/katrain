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


# 15 个短信字段各配一条 (env 名, env 字符串值, 装配后的期望值)。测试值全部**不同于
# 字段默认值**（不然 env 没接上也会碰巧通过），且**互不相同**（不然两个字段被
# 误接到同一个 env 变量也测不出来）。删掉任何一行 `data.setdefault(...)`，
# 这张表就能抓到对应那一个字段——之前只抽样 3 个时，删掉 SMS_PHONE_HOURLY
# 那行装配不会让任何测试变红。
_SMS_ENV_FIELDS = {
    "SMS_PROVIDER": ("KATRAIN_SMS_PROVIDER", "aliyun", "aliyun"),
    "SMS_ACCESS_KEY_ID": ("KATRAIN_SMS_ACCESS_KEY_ID", "test-ak-id", "test-ak-id"),
    "SMS_ACCESS_KEY_SECRET": ("KATRAIN_SMS_ACCESS_KEY_SECRET", "test-ak-secret", "test-ak-secret"),
    "SMS_SIGN_NAME": ("KATRAIN_SMS_SIGN_NAME", "测试签名", "测试签名"),
    "SMS_TEMPLATE_CODE": ("KATRAIN_SMS_TEMPLATE_CODE", "SMS_TEST_TPL", "SMS_TEST_TPL"),
    "SMS_CODE_TTL_SEC": ("KATRAIN_SMS_CODE_TTL_SEC", "301", 301),
    "SMS_COOLDOWN_SEC": ("KATRAIN_SMS_COOLDOWN_SEC", "61", 61),
    "SMS_PHONE_HOURLY": ("KATRAIN_SMS_PHONE_HOURLY", "6", 6),
    "SMS_PHONE_DAILY": ("KATRAIN_SMS_PHONE_DAILY", "12", 12),
    "SMS_IP_DAILY": ("KATRAIN_SMS_IP_DAILY", "22", 22),
    "SMS_MAX_ATTEMPTS": ("KATRAIN_SMS_MAX_ATTEMPTS", "7", 7),
    "SMS_DAILY_CAP_CN": ("KATRAIN_SMS_DAILY_CAP_CN", "302", 302),
    "SMS_DAILY_CAP_INTL": ("KATRAIN_SMS_DAILY_CAP_INTL", "52", 52),
    "SMS_ALLOW_CONSOLE": ("KATRAIN_SMS_ALLOW_CONSOLE", "1", True),
    "REGISTER_IP_DAILY": ("KATRAIN_REGISTER_IP_DAILY", "13", 13),
}


def test_sms_settings_are_wired_to_env_not_only_declared(monkeypatch):
    """字段声明了但 `Settings.__init__` 里没装配 ⇒ 线上设了 env 也不生效，
    表现是"限流参数怎么调都不动"这种没有任何报错的故障。两处都要写。

    覆盖任务书 Interfaces 一节列的全部 15 个字段（含 `REGISTER_IP_DAILY`），
    不是抽样几个——抽样版本对"漏写某一行装配"这种坏法免疫，因为没被抽到的
    那个字段坏了也不会被发现。
    """
    assert set(_SMS_ENV_FIELDS) == {
        "SMS_PROVIDER", "SMS_ACCESS_KEY_ID", "SMS_ACCESS_KEY_SECRET", "SMS_SIGN_NAME",
        "SMS_TEMPLATE_CODE", "SMS_CODE_TTL_SEC", "SMS_COOLDOWN_SEC", "SMS_PHONE_HOURLY",
        "SMS_PHONE_DAILY", "SMS_IP_DAILY", "SMS_MAX_ATTEMPTS", "SMS_DAILY_CAP_CN",
        "SMS_DAILY_CAP_INTL", "SMS_ALLOW_CONSOLE", "REGISTER_IP_DAILY",
    }, "字段表本身要覆盖 15 个 —— 少一个，那个字段就退回没测"

    for env_name, env_value, _expected in _SMS_ENV_FIELDS.values():
        monkeypatch.setenv(env_name, env_value)

    fresh = config.Settings()

    for field, (env_name, _env_value, expected) in _SMS_ENV_FIELDS.items():
        assert getattr(fresh, field) == expected, f"{field}（{env_name}）没接上 env 装配"


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


@pytest.mark.asyncio
async def test_aliyun_non_object_json_raises_sms_unreachable():
    """`resp.json()` 能成功解析出 list / str / null 等非对象，`.get()` 不存在。

    不单独判这一层的话，`body.get("Code", "")` 会抛裸 AttributeError，穿过调用方的
    `except SmsRejected` / `except SmsUnreachable` 变成 500，而额度/冷却记账
    一条都不执行——既没计入也没释放。语义上它和"非 JSON"同族：不知道收没收，保守计入。
    """
    def handler(request):
        return httpx.Response(200, json=[])

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


def test_sms_gate_actually_raises_when_the_lifespan_runs(monkeypatch):
    """端到端一点：真的调用 `_lifespan_server`，证明闸不是被注释掉/塞进死分支的摆设。

    上面两条源码字符串断言（`test_sms_gate_is_wired_into_the_server_lifespan` /
    `test_sms_gate_runs_before_any_database_work`）挡不住"注释掉调用"或"包进
    `if False:`"——它们只搜子串，注释和死分支里的调用照样匹配。这条不读源码，
    真的跑 `_lifespan_server`：如果闸没接上或被绕过，函数会往下走到
    `SQLAlchemyUserRepository(...).init_db()`（真连库），而不是在这里抛。
    抛在这里同时证明了「接上了」和「在任何 DB 动作之前」——因为如果它跑过了
    DB 初始化才抛，前面就该是别的报错（连库失败），不会是这条 RuntimeError。
    """
    import asyncio
    import logging

    from fastapi import FastAPI

    from katrain.web import server
    from katrain.web.core import config

    monkeypatch.setattr(config.settings, "SMS_PROVIDER", "")
    monkeypatch.setattr(config.settings, "KATRAIN_MODE", "server")
    with pytest.raises(RuntimeError, match="KATRAIN_SMS_PROVIDER"):
        asyncio.run(server._lifespan_server(FastAPI(), logging.getLogger("test-sms-gate")))
