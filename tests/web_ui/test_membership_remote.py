"""Membership and paid positions always use the bound cloud identity."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
import pytest_asyncio

from katrain.web.core.remote_client import RemoteAPIClient
from katrain.web.core.repository import RemoteServiceUnavailableError, RepositoryDispatcher


@pytest_asyncio.fixture
async def cloud():
    calls = []

    async def handle(request):
        calls.append(request)
        return httpx.Response(200, json={"authority": "cloud", "balance": 91})

    remote = RemoteAPIClient("http://cloud.test", "box-membership")
    await remote._client.aclose()
    remote._client = httpx.AsyncClient(base_url="http://cloud.test", transport=httpx.MockTransport(handle))
    remote.set_tokens("token-a", "refresh-a", user_id=7)
    local = MagicMock()
    local.balance = 25
    connectivity = SimpleNamespace(is_online=True)
    dispatcher = RepositoryDispatcher(connectivity, None, None, None, local, remote_client=remote)
    box = SimpleNamespace(remote=remote, dispatcher=dispatcher, calls=calls, local=local, connectivity=connectivity)
    yield box
    await remote.close()


OPERATIONS = [
    ("billing_catalog", (), "GET", "/api/v1/billing/catalog"),
    ("billing_usage", (), "GET", "/api/v1/billing/usage"),
    ("billing_quote", ({"product_code": "position", "position_id": "p-1"},), "POST", "/api/v1/billing/quotes"),
    ("billing_create_order", ({"quote_id": "q-1", "idempotency_key": "k-1"},), "POST", "/api/v1/billing/orders"),
    ("billing_list_orders", (), "GET", "/api/v1/billing/orders"),
    ("billing_get_order", ("o-1",), "GET", "/api/v1/billing/orders/o-1"),
    ("paid_position", ({"sgf_content": "(;SZ[19];B[pd])", "move_number": 1},), "POST", "/api/v1/analysis/positions"),
    ("paid_position_get", ("p-1",), "GET", "/api/v1/analysis/positions/p-1"),
]


@pytest.mark.parametrize("name,args,method,path", OPERATIONS)
async def test_membership_methods_proxy_only_to_cloud_with_expected_identity(cloud, name, args, method, path):
    remote_call = getattr(cloud.remote, name, None)
    dispatch_call = getattr(cloud.dispatcher, name, None)
    assert callable(remote_call) and callable(dispatch_call), f"Missing cloud-only membership method {name}"

    assert await dispatch_call(*args, expected_user_id=7) == {"authority": "cloud", "balance": 91}

    request = cloud.calls[0]
    assert (request.method, request.url.path) == (method, path)
    assert request.headers["authorization"] == "Bearer token-a"
    assert request.headers["X-StellaBox-Device-ID"] == "box-membership"
    assert (json.loads(request.content) if request.content else None) == (args[0] if method == "POST" else None)
    assert cloud.local.mock_calls == [] and cloud.local.balance == 25


@pytest.mark.parametrize("bound", [None, 8])
async def test_private_billing_requires_matching_cloud_binding_even_with_local_auth(cloud, bound):
    # Cookie/local authentication identifies 7; a local token must never become a cloud bearer.
    cloud.remote.bind_user(bound)
    with pytest.raises(httpx.HTTPStatusError) as error:
        await cloud.dispatcher.billing_usage(expected_user_id=7)
    assert error.value.response.status_code == 401
    assert error.value.response.json()["detail"]["code"] == "cloud_identity_changed"
    assert cloud.calls == [] and cloud.local.mock_calls == []


async def test_setting_new_tokens_without_user_clears_old_binding_until_bootstrap_binds(cloud):
    cloud.remote.set_tokens("token-b", "refresh-b")
    assert cloud.remote.bound_user_id is None
    with pytest.raises(httpx.HTTPStatusError) as error:
        await cloud.remote.billing_catalog(expected_user_id=7)
    assert error.value.response.status_code == 401
    assert cloud.calls == []


async def test_queued_request_is_rejected_before_sending_after_account_switch(cloud):
    call = cloud.remote.billing_create_order({"quote_id": "a-quote"}, expected_user_id=7)
    cloud.remote.set_tokens("token-b", "refresh-b", user_id=8)
    with pytest.raises(httpx.HTTPStatusError) as error:
        await call
    assert error.value.response.status_code == 401
    assert cloud.calls == []


@pytest.mark.parametrize("pause_at", ["first_401", "refresh", "first_200", "retried_200"])
async def test_account_switch_discards_old_results_and_never_retries_with_new_users_token(cloud, pause_at):
    entered, release = asyncio.Event(), asyncio.Event()
    requests = []

    async def handle(request):
        requests.append(request)
        if request.url.path == "/api/v1/auth/refresh":
            if pause_at == "refresh":
                entered.set()
                await release.wait()
            return httpx.Response(200, json={"access_token": "refreshed-a"})
        if request.headers["authorization"] == "Bearer token-a":
            if pause_at in ("first_401", "first_200"):
                entered.set()
                await release.wait()
            return httpx.Response(200 if pause_at == "first_200" else 401, json={"account": "a"})
        if pause_at == "retried_200":
            entered.set()
            await release.wait()
        return httpx.Response(200, json={"account": "a"})

    cloud.remote._client._transport = httpx.MockTransport(handle)
    pending = asyncio.create_task(cloud.remote.billing_create_order({"quote_id": "a-quote"}, expected_user_id=7))
    try:
        await asyncio.wait_for(entered.wait(), timeout=2)
        cloud.remote.set_tokens("token-b", "refresh-b", user_id=8)
        release.set()
        with pytest.raises(httpx.HTTPStatusError) as error:
            await pending
        assert error.value.response.status_code == 401
        assert all(request.headers.get("authorization") != "Bearer token-b" for request in requests)
        if pause_at in ("first_401", "first_200"):
            assert len(requests) == 1
        assert cloud.remote._access_token == "token-b"
        assert cloud.remote.bound_user_id == "8" and not cloud.remote.auth_required
    finally:
        release.set()
        if not pending.done():
            pending.cancel()
        await asyncio.gather(pending, return_exceptions=True)


@pytest.mark.parametrize("pause_at", ["request", "refresh"])
async def test_logout_and_login_as_same_user_still_invalidates_inflight_request(cloud, pause_at):
    entered, release = asyncio.Event(), asyncio.Event()

    async def handle(request):
        if (request.url.path == "/api/v1/auth/refresh") == (pause_at == "refresh"):
            entered.set()
            await release.wait()
        if request.url.path == "/api/v1/auth/refresh":
            return httpx.Response(200, json={"access_token": "stale-refresh-result"})
        return httpx.Response(401 if pause_at == "refresh" else 200, json={"balance": 999})

    cloud.remote._client._transport = httpx.MockTransport(handle)
    pending = asyncio.create_task(cloud.remote.billing_usage(expected_user_id=7))
    try:
        await asyncio.wait_for(entered.wait(), timeout=2)
        cloud.remote.clear_tokens()
        # Deliberately restore identical credentials: generation must distinguish logins.
        cloud.remote.set_tokens("token-a", "refresh-a", user_id=7)
        release.set()
        with pytest.raises(httpx.HTTPStatusError) as error:
            await pending
        assert error.value.response.status_code == 401
        assert cloud.remote._access_token == "token-a" and not cloud.remote.auth_required
    finally:
        release.set()
        if not pending.done():
            pending.cancel()
        await asyncio.gather(pending, return_exceptions=True)


async def test_same_identity_can_refresh_and_retry_with_refreshed_token(cloud):
    seen = []

    async def handle(request):
        seen.append(request)
        if request.url.path == "/api/v1/auth/refresh":
            assert json.loads(request.content) == {"refresh_token": "refresh-a"}
            return httpx.Response(200, json={"access_token": "refreshed-a"})
        return httpx.Response(
            200 if request.headers["authorization"] == "Bearer refreshed-a" else 401, json={"authority": "cloud"}
        )

    cloud.remote._client._transport = httpx.MockTransport(handle)
    assert await cloud.remote.billing_usage(expected_user_id=7) == {"authority": "cloud"}
    assert [request.headers.get("authorization") for request in seen] == ["Bearer token-a", None, "Bearer refreshed-a"]
    assert cloud.remote.bound_user_id == "7" and not cloud.remote.auth_required


@pytest.mark.parametrize("failure", ["connect", "server"])
async def test_refresh_outage_is_unavailable_instead_of_invalidating_login(cloud, failure):
    async def handle(request):
        if request.url.path == "/api/v1/auth/refresh":
            if failure == "connect":
                raise httpx.ConnectError("offline")
            return httpx.Response(503)
        return httpx.Response(401)

    cloud.remote._client._transport = httpx.MockTransport(handle)
    with pytest.raises(RemoteServiceUnavailableError):
        await cloud.dispatcher.billing_usage(expected_user_id=7)
    assert not cloud.remote.auth_required
    assert cloud.local.mock_calls == []


@pytest.mark.parametrize("status", [400, 401, 403, 404, 409, 422, 429, 500, 503])
async def test_cloud_errors_preserve_4xx_and_never_fall_back_to_local_ledger(cloud, status):
    upstream = {"detail": {"code": "cloud_error", "message": "cloud refused"}}

    async def handle(request):
        return httpx.Response(status, json=upstream)

    cloud.remote._client._transport = httpx.MockTransport(handle)
    expected_error = httpx.HTTPStatusError if status < 500 else RemoteServiceUnavailableError
    with pytest.raises(expected_error) as error:
        await cloud.dispatcher.billing_create_order({"quote_id": "q-1"}, expected_user_id=7)
    if status < 500:
        assert error.value.response.status_code == status
        assert error.value.response.json() == upstream
    assert cloud.local.mock_calls == [] and cloud.local.balance == 25


@pytest.mark.parametrize("failure", ["offline", "connect", "timeout"])
async def test_offline_membership_is_unavailable_and_does_not_spend_local_balance(cloud, failure):
    async def handle(request):
        raise httpx.ConnectError("offline") if failure == "connect" else httpx.ReadTimeout("timed out")

    cloud.remote._client._transport = httpx.MockTransport(handle)
    cloud.connectivity.is_online = failure != "offline"
    with pytest.raises(RemoteServiceUnavailableError):
        await cloud.dispatcher.billing_create_order({"quote_id": "q-1"}, expected_user_id=7)
    assert cloud.local.mock_calls == [] and cloud.local.balance == 25


REPORT_WRITES = [
    ("reports_create", "create_report", "/api/v1/reports/"),
    ("reports_retry", "retry_report", "/api/v1/reports/7/retry"),
]


@pytest.mark.parametrize("dispatcher_method,remote_method,path", REPORT_WRITES)
async def test_paid_report_writes_forward_quote_and_idempotency_body(cloud, dispatcher_method, remote_method, path):
    payload = {"quote_token": "signed-quote-a", "idempotency_key": "report-key-a"}
    if dispatcher_method == "reports_create":
        payload.update(user_game_id="cloud-game-a", report_type="deep")
    args = (payload,) if dispatcher_method == "reports_create" else (7, payload)

    assert await getattr(cloud.dispatcher, dispatcher_method)(*args, expected_user_id=7) == {
        "authority": "cloud",
        "balance": 91,
    }

    assert len(cloud.calls) == 1
    assert (cloud.calls[0].method, cloud.calls[0].url.path) == ("POST", path)
    assert json.loads(cloud.calls[0].content) == payload
    assert cloud.calls[0].headers["authorization"] == "Bearer token-a"
    assert cloud.local.mock_calls == []


@pytest.mark.parametrize("dispatcher_method,remote_method,path", REPORT_WRITES)
async def test_paid_report_writes_reject_changed_cloud_identity(cloud, dispatcher_method, remote_method, path):
    payload = {"quote_token": "signed-quote-a", "idempotency_key": "report-key-a"}
    args = (payload,) if dispatcher_method == "reports_create" else (7, payload)
    cloud.remote.set_tokens("token-b", "refresh-b", user_id=8)

    for client, name in ((cloud.dispatcher, dispatcher_method), (cloud.remote, remote_method)):
        with pytest.raises(httpx.HTTPStatusError) as error:
            await getattr(client, name)(*args, expected_user_id=7)
        assert error.value.response.status_code == 401
        assert error.value.response.json()["detail"]["code"] == "cloud_identity_changed"
    assert cloud.calls == [] and cloud.local.mock_calls == []
