"""短信供应商抽象。**零新增依赖**：标准库 hmac/hashlib/base64/urllib.parse + 已有的 httpx。

不用阿里云官方 SDK 的两个理由：(1) 生产依赖清单是 release 分支独有的 hash-pinned
`requirements-web-runtime.txt`，往 `requirements-web.txt` 加包只会**在生产运行时**
ImportError（F8）；(2) 官方 SDK 是同步的，而这里必须 async —— 单进程下同步阻塞拖垮整站。

**两类失败必须分开，这不是风格问题，是钱：**
    SmsRejected     供应商明确拒收（HTTP 200 但 Code != OK）⇒ 确定没计费 ⇒ 不占日额度
    SmsUnreachable  超时 / 连不上 / 5xx / 非 JSON ⇒ 不知道它收没收 ⇒ 保守计入日额度
合成一类的后果：`send-code` 不鉴权，攻击者拿格式合法但一定被拒的号（`+9991234567`）
零成本把全站日额度打满，当天所有人拿不到码，而我们一分钱短信费都没花 —— 花掉的是可用性。
"""
import base64
import hashlib
import hmac
import urllib.parse
import uuid
from datetime import datetime, timezone

import httpx

from katrain.web.core.config import settings
from katrain.web.core.phone import mask_e164


class SmsProviderError(Exception):
    """把码交给供应商这一步失败了。调用方**必须**在两个子类之间分流，
    不要只 `except SmsProviderError` —— 那等于又把两件事合成了一件。"""


class SmsRejected(SmsProviderError):
    """供应商**明确拒收**：HTTP 200，但响应体里 Code != OK。
    含义是"这条没发出去，也没计费" ⇒ 不计入日额度，也不置同号冷却。"""


class SmsUnreachable(SmsProviderError):
    """超时 / 连不上 / 5xx / 响应体不是 JSON。
    含义是"不知道它收没收" ⇒ 保守计入日额度，但不置同号冷却
    （一次抖动不该把用户锁 60 秒）。"""


class SmsProvider:
    async def send(self, phone_e164: str, code: str, is_intl: bool) -> None:
        raise NotImplementedError


class ConsoleProvider(SmsProvider):
    """开发用。只打印，不发送。生产被 assert_sms_provider_is_configured 挡住。"""

    async def send(self, phone_e164: str, code: str, is_intl: bool) -> None:
        # 打掩码不打明文：这行会进开发机的终端和日志文件。
        print(f"[SMS console] to={mask_e164(phone_e164)} intl={is_intl} code={code}")


class AliyunProvider(SmsProvider):
    # 阿里云要求的百分号编码：空格→%20、`*`→%2A、`~` 不编码。
    # Python 的 quote 本来就不编 `~`、且从不产生 `+`，所以 safe="~" 正好等价。
    _SIGN_SAFE = "~"

    def __init__(self, access_key_id, access_key_secret, sign_name, template_code, transport=None):
        self.access_key_id = access_key_id
        self.access_key_secret = access_key_secret
        self.sign_name = sign_name
        self.template_code = template_code
        # 只给测试注入 httpx.MockTransport；生产传 None（httpx 用默认传输）。
        self._transport = transport

    @staticmethod
    def _endpoint(is_intl: bool) -> str:
        # 国际那条不需要签名与模板报备 ⇒ 它是最先能端到端跑通的通道（D-U4）。
        return (
            "https://dysmsapi.ap-southeast-1.aliyuncs.com/"
            if is_intl
            else "https://dysmsapi.aliyuncs.com/"
        )

    @staticmethod
    def _action(is_intl: bool) -> str:
        return "SendMessageToGlobe" if is_intl else "SendSms"

    def _string_to_sign(self, params: dict) -> str:
        """阿里云 RPC 签名的规范化串。

        **单独暴露成方法是为了能被单测钉死**：只断言"签名长 28 字符"或"与字典
        顺序无关"是假绿 —— 任何 base64(HMAC-SHA1) 都是 28 字符，任何做了
        sorted() 的实现都与顺序无关，一个拼错的 string-to-sign 照样通过。
        """
        canon = "&".join(
            f"{urllib.parse.quote(k, safe=self._SIGN_SAFE)}="
            f"{urllib.parse.quote(str(v), safe=self._SIGN_SAFE)}"
            for k, v in sorted(params.items())
        )
        return "GET&%2F&" + urllib.parse.quote(canon, safe=self._SIGN_SAFE)

    def _sign(self, params: dict) -> str:
        """HMAC-SHA1(secret + "&") → base64。那个尾随 `&` 是签名规范的一部分。"""
        mac = hmac.new(
            (self.access_key_secret + "&").encode(),
            self._string_to_sign(params).encode(),
            hashlib.sha1,
        )
        return base64.b64encode(mac.digest()).decode()

    async def send(self, phone_e164: str, code: str, is_intl: bool) -> None:
        params = {
            "Action": self._action(is_intl),
            "Version": "2018-05-01" if is_intl else "2017-05-25",
            "Format": "JSON",
            "AccessKeyId": self.access_key_id,
            "SignatureMethod": "HMAC-SHA1",
            "SignatureVersion": "1.0",
            "SignatureNonce": uuid.uuid4().hex,
            "Timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        if is_intl:
            params.update({"To": phone_e164, "Message": f"Your verification code is {code}"})
        else:
            params.update(
                {
                    "PhoneNumbers": phone_e164[len("+86"):],
                    "SignName": self.sign_name,
                    "TemplateCode": self.template_code,
                    "TemplateParam": f'{{"code":"{code}"}}',
                }
            )
        params["Signature"] = self._sign(params)

        try:
            async with httpx.AsyncClient(timeout=3.0, transport=self._transport) as client:
                resp = await client.get(self._endpoint(is_intl), params=params)
        except Exception as exc:
            # 连不上 / 超时：**不知道**阿里收没收 ⇒ 调用方保守计入日额度。
            raise SmsUnreachable(f"短信供应商不可达: {exc}") from exc

        if resp.status_code >= 500:
            raise SmsUnreachable(f"短信供应商 {resp.status_code}")
        try:
            body = resp.json()
        except ValueError as exc:
            raise SmsUnreachable(f"短信供应商返回了非 JSON（{resp.status_code}）") from exc

        if str(body.get("Code", "")).upper() != "OK":
            # HTTP 200 且 Code != OK：阿里**明确拒收**，确定没计费。
            raise SmsRejected(f"短信供应商拒收: {body.get('Code')} {body.get('Message')}")


def get_provider() -> SmsProvider:
    """按配置造一个提供方。

    未知名在这里抛，**但真正的防线是启动闸** —— `assert_sms_provider_is_configured()`
    在 lifespan 里就拒绝未知名，所以生产走不到这条 raise（走到了说明有人绕过了闸）。
    """
    name = (settings.SMS_PROVIDER or "").strip()
    if name == "console":
        return ConsoleProvider()
    if name == "aliyun":
        return AliyunProvider(
            access_key_id=settings.SMS_ACCESS_KEY_ID,
            access_key_secret=settings.SMS_ACCESS_KEY_SECRET,
            sign_name=settings.SMS_SIGN_NAME,
            template_code=settings.SMS_TEMPLATE_CODE,
        )
    raise SmsProviderError(f"未知的 SMS_PROVIDER={name!r}")
