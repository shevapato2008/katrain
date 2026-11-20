"""Isolated AF_UNIX protocol checks; no real identity service or cloud."""
import asyncio
import json
import tempfile

import pytest

from katrain.web.core.identity_go_client import verify_go_operation, IdentityGoUnavailable


@pytest.mark.asyncio
@pytest.mark.parametrize('result', [
    {'operation': 'bootstrap', 'generation': 9, 'username': 'alice'},
    {'operation': 'clear', 'generation': 8},
    {'operation': 'bootstrap', 'generation': 8, 'username': 'alice', 'remote_refresh_token': 'secret'},
    {'operation': 'bootstrap', 'generation': True, 'username': 'alice'},
    {'operation': 'bootstrap', 'generation': 8},
])
async def test_go_client_rejects_wrong_scope_or_secret_bearing_identity_reply(result):
    async def handle(reader, writer):
        value = json.loads(await reader.read())
        writer.write(json.dumps({'version': 1, 'request_id': value['request_id'], 'result': result}).encode())
        await writer.drain()
        writer.close()
        await writer.wait_closed()
    with tempfile.TemporaryDirectory(dir='/tmp', prefix='go-client-') as directory:
        async with await asyncio.start_unix_server(handle, path=directory + '/socket'):
            with pytest.raises(IdentityGoUnavailable):
                await verify_go_operation(directory + '/socket', 'a' * 64, 'bootstrap', 8)


@pytest.mark.asyncio
async def test_go_client_accepts_only_correlated_public_approval():
    async def handle(reader, writer):
        value = json.loads(await reader.read())
        assert value['method'] == 'verify_go_operation'
        assert value['params'] == {'operation_id': 'a' * 64, 'operation': 'bootstrap', 'generation': 8}
        writer.write(json.dumps({'version': 1, 'request_id': value['request_id'], 'result': {
            'operation': 'bootstrap', 'generation': 8, 'username': 'alice', 'public_username': 'Alice',
        }}).encode())
        await writer.drain()
        writer.close()
        await writer.wait_closed()
    with tempfile.TemporaryDirectory(dir='/tmp', prefix='go-client-') as directory:
        async with await asyncio.start_unix_server(handle, path=directory + '/socket'):
            assert (await verify_go_operation(directory + '/socket', 'a' * 64, 'bootstrap', 8))['username'] == 'alice'
