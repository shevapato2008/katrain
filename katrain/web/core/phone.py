"""E.164 手机号归一化。**手写，不引第三方号段库**（见计划 Global Constraints #1）。

我们只需要三件事：把用户输入存成 E.164 规范形式、判断"该走国内还是国际短信通道"、
给用户看一个掩码形式。不判断号段是否真实存在 —— 那是运营商的事，发出去就知道了。
"""
import re

# E.164：`+` 后 7-15 位数字，首位不为 0。这是**全球下限**，不是中国大陆的下限。
# 不许拿它去挡短号：真实存在 7 位的国际号（纽埃 +683 的订户号是 4 位），
# 把这里抬到 11 位等于把所有短国家码国际号一起误杀。
_E164_RE = re.compile(r"^\+[1-9]\d{6,14}$")
_SEPARATORS = re.compile(r"[\s\-().]")

# 中国大陆：手机号恰好 11 位、首位为 1。座机与短号一律不收 —— 我们只发短信。
# `normalize_e164` 的长度闸与 `is_domestic` 的通道判别共用这两个常量。
CN_CC = "86"
CN_NATIONAL_LEN = 11
_CN_MOBILE_RE = re.compile(r"^1\d{%d}$" % (CN_NATIONAL_LEN - 1))

DEFAULT_REGION_CC = CN_CC

# 只用于**显示**的国家码切分表。认不出来就整体打码，不猜。
_DISPLAY_CC = frozenset({"852", "853", "886", "86", "81", "82", "91", "44", "1"})


def normalize_e164(raw: str, default_region_cc: str = DEFAULT_REGION_CC) -> str:
    """把用户输入归一成 `+<国家码><号码>`。无法归一时抛 ValueError（**不返回 None**：
    静默的 None 会一路流到库里变成"未绑定"，而用户以为自己绑上了）。"""
    if not raw or not raw.strip():
        raise ValueError("手机号为空")
    s = _SEPARATORS.sub("", raw.strip())
    if s.startswith("00"):
        s = "+" + s[2:]
    elif not s.startswith("+"):
        # 裸号：按默认区号补。国内号习惯写成 11 位裸号，也可能带一个国内长途前缀 0。
        s = "+" + default_region_cc + s.lstrip("0")
    if not _E164_RE.match(s):
        raise ValueError(f"不是合法的 E.164 手机号: {raw!r}")
    # 中国大陆的下限。**挂在归一后的号码上，不挂在 default_region_cc 上** ——
    # 这样显式写成 "+8612345" 的短号也一样被挡。没有这一条，"12345" 会变成
    # "+8612345"（7 位数字）被上面的全球下限放过，然后因为 is_domestic 为 False
    # 被路由到国际通道、计进那个贵的日额度计数器。
    if s.startswith("+" + CN_CC):
        national = s[1 + len(CN_CC) :]
        if not _CN_MOBILE_RE.match(national):
            raise ValueError(f"不是合法的中国大陆手机号（应为 1 开头的 {CN_NATIONAL_LEN} 位）: {raw!r}")
    return s


def is_domestic(e164: str) -> bool:
    """是否走国内通道（阿里云 SendSms）。**只有中国大陆 11 位号**。

    港澳台走国际通道（SendMessageToGlobe）—— 那条不需要签名与模板报备。
    位数不对的 +86 号一律按国际处理：`normalize_e164` 今天已经不产出这种号了，
    这里是纵深（手工插的行、将来放宽的归一规则）。
    """
    return e164.startswith("+" + CN_CC) and len(e164) == 1 + len(CN_CC) + CN_NATIONAL_LEN


def mask_e164(e164: str) -> str:
    """给用户看的掩码形式。原始号只从专用鉴权端点以这个形式出去。"""
    if not e164.startswith("+") or not e164[1:].isdigit():
        raise ValueError("mask_e164 只接受 E.164")
    body = e164[1:]
    for cc_len in (3, 2, 1):   # 长的先试，否则 "+86…" 会被 "+8…" 抢走
        cc, rest = body[:cc_len], body[cc_len:]
        if cc in _DISPLAY_CC and len(rest) >= 7:
            return f"+{cc} {rest[:3]}****{rest[-4:]}"
    # 认不出国家码：不猜切分（猜错会把国家码的位数当号码位数漏出去），整体只留末 4 位。
    return "+" + "*" * max(0, len(body) - 4) + body[-4:]
