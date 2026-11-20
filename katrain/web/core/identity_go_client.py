"""Fixed identity UDS client for the isolated Go UID. No credential fallback."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import re
import socket
import time
import uuid

MAX_REQUEST = 8 * 1024 * 1024
MAX_REPLY = 8 * 1024 * 1024
TIMEOUT = 15.0


class IdentityGoUnavailable(RuntimeError):
    pass


def _pairs(items):
    value = {}
    for key, item in items:
        if key in value:
            raise ValueError('duplicate field')
        value[key] = item
    return value


def _exchange(path, method, params):
    request_id = uuid.uuid4().hex
    try:
        if not Path(path).is_absolute():
            raise ValueError()
        payload = json.dumps({'version': 1, 'request_id': request_id, 'method': method, 'params': params},
                             allow_nan=False, ensure_ascii=True, separators=(',', ':')).encode('ascii')
        if len(payload) > MAX_REQUEST:
            raise ValueError()
        deadline = time.monotonic() + TIMEOUT
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
            conn.settimeout(2)
            conn.connect(str(path))
            conn.settimeout(max(0.001, deadline - time.monotonic()))
            conn.sendall(payload)
            conn.shutdown(socket.SHUT_WR)
            raw = bytearray()
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError()
                conn.settimeout(remaining)
                chunk = conn.recv(min(65536, MAX_REPLY + 1 - len(raw)))
                if not chunk:
                    break
                raw.extend(chunk)
                if len(raw) > MAX_REPLY:
                    raise ValueError()
        if not raw.startswith(b'{') or not raw.endswith(b'}'):
            raise ValueError()
        value = json.loads(raw, object_pairs_hook=_pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        if (not isinstance(value, dict) or set(value) != {'version', 'request_id', 'result'}
                or type(value['version']) is not int or value['version'] != 1 or value['request_id'] != request_id):
            raise ValueError()
        return value['result']
    except (OSError, ValueError, TypeError, RecursionError):
        raise IdentityGoUnavailable('Go identity unavailable') from None


async def verify_go_operation(path, operation_id, operation, generation):
    if (not isinstance(operation_id, str) or re.fullmatch('[a-f0-9]{64}', operation_id) is None
            or operation not in {'bootstrap', 'guest-bootstrap', 'clear'} or type(generation) is not int or generation <= 0):
        raise IdentityGoUnavailable('Go identity unavailable')
    result = await asyncio.to_thread(_exchange, path, 'verify_go_operation', {
        'operation_id': operation_id, 'operation': operation, 'generation': generation,
    })
    if (not isinstance(result, dict) or not {'operation', 'generation'} <= set(result)
            or not set(result) <= {'operation', 'generation', 'username', 'public_username'}
            or result['operation'] != operation or type(result['generation']) is not int or result['generation'] != generation):
        raise IdentityGoUnavailable('Go identity unavailable')
    if operation == 'clear':
        if set(result) != {'operation', 'generation'}:
            raise IdentityGoUnavailable('Go identity unavailable')
    elif (not isinstance(result.get('username'), str) or not result['username'].strip() or len(result['username']) > 128
            or (result.get('public_username') is not None and
                (not isinstance(result['public_username'], str) or len(result['public_username']) > 128))):
        raise IdentityGoUnavailable('Go identity unavailable')
    return result


async def cloud_request(path, generation, operation, arguments, body, params):
    result = await asyncio.to_thread(_exchange, path, 'go_cloud_request', {
        'generation': generation, 'operation': operation, 'arguments': arguments, 'body': body, 'query': params,
    })
    if (not isinstance(result, dict) or set(result) != {'status', 'body'}
            or type(result['status']) is not int or not 200 <= result['status'] <= 599):
        raise IdentityGoUnavailable('Go identity unavailable')
    return result
