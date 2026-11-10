from datetime import datetime, timedelta, timezone


def test_beijing_week_boundary_and_30_day_term():
    from katrain.web.core.membership import week_window

    before = datetime(2026, 11, 1, 15, 59, tzinfo=timezone.utc)
    after = before + timedelta(minutes=1)
    k1, s1, e1 = week_window(before)
    k2, s2, e2 = week_window(after)
    assert k1 != k2
    assert e1 == s2 == after
    assert e2 - s2 == timedelta(days=7)
