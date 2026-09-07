"""Task 1: E.164 归一化 —— 接受什么、拒绝什么、以什么形式给用户看。"""

import pytest

from katrain.web.core.phone import is_domestic, mask_e164, normalize_e164


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("13800138000", "+8613800138000"),        # 裸国内号，按默认区号补
        ("+86 138 0013 8000", "+8613800138000"),  # 空格
        ("+86-138-0013-8000", "+8613800138000"),  # 连字符
        ("008613800138000", "+8613800138000"),    # 00 国际前缀
        ("+85298765432", "+85298765432"),         # 香港
        ("+14155552671", "+14155552671"),         # 美国
    ],
)
def test_normalize_accepts_and_canonicalizes(raw, expected):
    assert normalize_e164(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "abc",
        "+",
        "+86",
        "12345",                  # 裸短号：补完区号是 +8612345，**必须**被国内长度闸挡下
        "+8613800138000123456",   # 超长
        "+0123456789",            # 国家码首位为 0
        "+861380013800",          # +86 但只有 10 位本体
        "+8623800138000",         # +86、11 位，但首位不是 1（座机/短号，发不了短信）
    ],
)
def test_normalize_rejects_garbage(raw):
    """`None` 不在这张表里：passlib 之外这里也有同款陷阱 —— 今天
    `normalize_e164(None)` 已经在第一行 `if not raw` 上抛了，把它写进来是一条
    **拆掉实现也不会红**的假绿断言。表里每一条都是真的靠新增判据才红的。"""
    with pytest.raises(ValueError):
        normalize_e164(raw)


def test_short_country_code_international_is_not_collateral_damage():
    """挡住 `"12345"` 的那条下限**只能挂在 +86 上**。

    最省事的「修法」是把 `_E164_RE` 的 `\\d{6,14}` 抬成 `\\d{10,14}` —— 那样
    `"12345"` 确实红转绿，代价是所有短国家码国际号一起被误杀。纽埃 `+683` 的
    订户号是 4 位，`+6831234` 是合法 E.164。这条用例就是那个抬法的红灯。"""
    assert normalize_e164("+6831234") == "+6831234"
    assert is_domestic("+6831234") is False


def test_normalize_is_idempotent():
    once = normalize_e164("13800138000")
    assert normalize_e164(once) == once


def test_is_domestic_only_for_mainland_11_digit():
    assert is_domestic("+8613800138000") is True
    assert is_domestic("+85298765432") is False     # 香港走国际通道
    assert is_domestic("+14155552671") is False
    # `normalize_e164` 现在已经不会产出这种号了；这条是**纵深**：库里的行可能是
    # 手工插的、也可能是将来放宽了归一规则的。位数不对的 +86 一律不许当国内号
    # 去发国内模板 —— 那种失败的报错是运营商的、我们解释不了。
    assert is_domestic("+861380013800") is False


def test_mask_keeps_country_code_and_last_four():
    assert mask_e164("+8613800138000") == "+86 138****8000"
    assert mask_e164("+14155552671") == "+1 415****2671"
    assert mask_e164("+85298765432") == "+852 987****5432"
    # 中段真的没了 —— 只断言等号的话，一个「原样返回」的实现也能凑出格式来。
    assert "0013" not in mask_e164("+8613800138000")


def test_mask_falls_back_to_full_mask_for_unknown_country_code():
    """认不出国家码就不猜切分。猜错了会把国家码的位数当成号码的位数漏出去。"""
    assert mask_e164("+6831234") == "+***1234"


def test_mask_rejects_non_e164():
    with pytest.raises(ValueError):
        mask_e164("8613800138000")   # 没有前导 +
    with pytest.raises(ValueError):
        mask_e164("+86-138")         # 本体不是纯数字
