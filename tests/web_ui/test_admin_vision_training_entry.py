"""Training opt-in changes only the dedicated local bind; does not launch training."""

import pytest


@pytest.mark.parametrize(
    "env,switch,expected", [("test", "1", "127.0.0.1"), ("test", "0", "0.0.0.0"), ("prod", "1", "0.0.0.0")]
)
def test_training_entry_binds_loopback_when_explicitly_requested(monkeypatch, env, switch, expected):
    from katrain.web.admin import __main__ as entry

    monkeypatch.setenv("KATRAIN_ADMIN_ENV", env)
    monkeypatch.setenv("KATRAIN_ADMIN_VISION_TRAINING", switch)
    monkeypatch.delenv("KATRAIN_ADMIN_VISION_LOCAL", raising=False)
    observed = []
    monkeypatch.setattr(entry, "create_admin_app", lambda **kwargs: observed.append(kwargs) or object())
    monkeypatch.setattr(entry.uvicorn, "run", lambda app, **kwargs: observed.append(kwargs))
    entry.main()
    assert observed[0]["bind_host"] == observed[1]["host"] == expected
