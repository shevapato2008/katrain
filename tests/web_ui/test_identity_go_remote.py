import httpx
import pytest

from katrain.web.core.config import settings
from katrain.web.core.remote_client import RemoteAPIClient, CloudIdentityChangedError


@pytest.mark.asyncio
async def test_identity_remote_keeps_local_owner_checks_without_any_cloud_tokens(monkeypatch):
    from katrain.web.core import identity_go_client
    monkeypatch.setattr(settings, 'KATRAIN_IDENTITY_GO_SOCKET', '/test/go.sock')
    monkeypatch.setattr(settings, 'KATRAIN_MODE', 'board')
    monkeypatch.setattr(settings, 'KATRAIN_BOX_SSO', True)
    client = RemoteAPIClient('https://fixed.invalid', 'device')
    seen = []
    async def cloud(path, generation, operation, arguments, body, params):
        seen.append((path, generation, operation, arguments, body, params))
        return {'status': 200, 'body': {'credits': 10}}
    monkeypatch.setattr(identity_go_client, 'cloud_request', cloud)
    client.bind_identity(70, user_id=1)
    assert client.cloud_session_is(1)
    assert client._access_token is None and client._refresh_token is None
    assert await client.billing_usage(expected_user_id=1) == {'credits': 10}
    assert seen == [('/test/go.sock', 70, 'billing_usage', {}, None, None)]
    with pytest.raises(CloudIdentityChangedError):
        await client.billing_usage(expected_user_id=2)
    with pytest.raises(ValueError):
        client.set_tokens('forbidden', 'forbidden')
    client.clear_tokens()
    assert not client.is_authenticated
    with pytest.raises(CloudIdentityChangedError):
        await client.billing_usage(expected_user_id=1)
    assert len(seen) == 1
    await client.close()


@pytest.mark.asyncio
async def test_identity_remote_cannot_forward_url_header_or_unknown_method(monkeypatch):
    monkeypatch.setattr(settings, 'KATRAIN_IDENTITY_GO_SOCKET', '/test/go.sock')
    monkeypatch.setattr(settings, 'KATRAIN_MODE', 'board')
    monkeypatch.setattr(settings, 'KATRAIN_BOX_SSO', True)
    client = RemoteAPIClient('https://fixed.invalid', 'device')
    client.bind_identity(70, user_id=1)
    for method, path in [('POST', '/api/v1/auth/refresh'), ('GET', 'https://evil.invalid/api/v1/billing/usage'),
                         ('GET', '/api/v1/billing/usage?url=evil'), ('GET', '/admin')]:
        with pytest.raises((ValueError, httpx.HTTPError)):
            await client._request(method, path)
    await client.close()


@pytest.mark.asyncio
async def test_identity_phone_reauth_refusal_does_not_replay_or_logout(monkeypatch):
    from katrain.web.core import identity_go_client
    monkeypatch.setattr(settings, 'KATRAIN_IDENTITY_GO_SOCKET', '/test/go.sock')
    monkeypatch.setattr(settings, 'KATRAIN_MODE', 'board')
    monkeypatch.setattr(settings, 'KATRAIN_BOX_SSO', True)
    client = RemoteAPIClient('https://fixed.invalid', 'device')
    seen = []
    async def cloud(*args):
        seen.append(args)
        return {'status': 401, 'body': {'detail': {'code': 'bind_reauth_failed'}}}
    monkeypatch.setattr(identity_go_client, 'cloud_request', cloud)
    client.bind_identity(70, user_id=1)
    with pytest.raises(httpx.HTTPStatusError):
        await client.phone_bind({'challenge_id': 'a' * 16, 'code': '123456', 'flow_id': 'a' * 22,
                                 'current_password': 'wrong'}, expected_user_id=1)
    assert len(seen) == 1
    assert client.cloud_session_is(1)
    await client.close()


def test_fixed_go_contract_accepts_current_frozen_ladder_recipes():
    from katrain.core import ladder
    from katrain.web.core.identity_go_contract import describe
    for level in ladder.LADDER_LEVELS:
        if level.recipe is None:
            continue
        body = {'game_id': 'a' * 32, 'user_color': 'B', 'result': 'inconclusive', 'game_type': 'ai_ladder_ranked',
                'opponent': {'rung': level.rung, 'rank_name': level.rank_name,
                             'config_snapshot': {'config_digest': 'a' * 64, 'config_version': ladder.LADDER_VERSION,
                                                 'recipe_identity': 'a' * 64, 'recipe': level.recipe.to_dict()},
                             'certification_status': level.certification_status, 'availability': level.availability,
                             'route': level.route}}
        assert describe('settle_ai_ladder_ranked', {}, body)[2] == body


@pytest.mark.asyncio
async def test_normal_five_category_burst_queues_with_two_cloud_slots(monkeypatch):
    import asyncio
    from katrain.web.core import identity_go_client
    monkeypatch.setattr(settings, 'KATRAIN_IDENTITY_GO_SOCKET', '/test/go.sock')
    monkeypatch.setattr(settings, 'KATRAIN_MODE', 'board')
    monkeypatch.setattr(settings, 'KATRAIN_BOX_SSO', True)
    client = RemoteAPIClient('https://fixed.invalid', 'device')
    active = peak = 0
    async def cloud(*args):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return {'status': 200, 'body': []}
    monkeypatch.setattr(identity_go_client, 'cloud_request', cloud)
    try:
        assert await asyncio.gather(*(client.get_problems('15k', str(category)) for category in range(5))) == [[]] * 5
        assert peak == 2
    finally:
        await client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('status,required', [(401, True), (503, False)])
async def test_identity_auth_refusal_pauses_cloud_but_outage_stays_retryable(monkeypatch, status, required):
    from katrain.web.core import identity_go_client
    monkeypatch.setattr(settings, 'KATRAIN_IDENTITY_GO_SOCKET', '/test/go.sock')
    monkeypatch.setattr(settings, 'KATRAIN_MODE', 'board')
    monkeypatch.setattr(settings, 'KATRAIN_BOX_SSO', True)
    client = RemoteAPIClient('https://fixed.invalid', 'device')
    async def cloud(*args):
        return {'status': status, 'body': {'detail': {'code': 'authentication_required' if status == 401 else 'unavailable'}}}
    monkeypatch.setattr(identity_go_client, 'cloud_request', cloud)
    client.bind_identity(70, user_id=1)
    try:
        with pytest.raises(httpx.HTTPStatusError):
            await client.billing_catalog(expected_user_id=1)
        assert client.auth_required is required
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_queued_go_request_cannot_change_to_next_identity(monkeypatch):
    import asyncio
    from katrain.web.core import identity_go_client
    monkeypatch.setattr(settings, 'KATRAIN_IDENTITY_GO_SOCKET', '/test/go.sock')
    monkeypatch.setattr(settings, 'KATRAIN_MODE', 'board')
    monkeypatch.setattr(settings, 'KATRAIN_BOX_SSO', True)
    client = RemoteAPIClient('https://fixed.invalid', 'device')
    started, finish = asyncio.Event(), asyncio.Event()
    calls = []
    async def cloud(*args):
        calls.append(args)
        if len(calls) == 2:
            started.set()
        await finish.wait()
        return {'status': 200, 'body': {}}
    monkeypatch.setattr(identity_go_client, 'cloud_request', cloud)
    client.bind_identity(70, user_id=1)
    tasks = [asyncio.create_task(client.billing_catalog(expected_user_id=1)) for _ in range(3)]
    try:
        await started.wait()
        client.bind_identity(71, user_id=2)
        finish.set()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        assert all(isinstance(result, CloudIdentityChangedError) for result in results)
        assert len(calls) == 2
    finally:
        finish.set()
        await asyncio.gather(*tasks, return_exceptions=True)
        await client.close()
