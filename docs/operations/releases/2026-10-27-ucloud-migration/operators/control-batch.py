#!/usr/bin/env python3
"""Fixed seven interval cron controls; prepare/status read only, pause/restore explicit CAS.
Run on the expected host. All database credentials stay inside the explicit container.
No loop jobs, run_now commands, schedulers, or business tables are touched.
"""
import argparse
import datetime as dt
import fcntl
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys
import tempfile

JOBS = ('fetch_list', 'poll_moves', 'poll_pandanet', 'translate', 'fetch_upcoming', 'cleanup', 'tutorial_backup')
COLUMNS = ('job_name', 'paused', 'reason', 'changed_at', 'changed_by')
ROLES = ('old-prod', 'new-stage', 'new-prod', 'test')
CONTAINERS = {'katrain-ucloud-katrain-web-1', 'katrain-ucloud-katrain-cron-1', 'katrain-cron'}
ROLE_TARGETS = {
    'test': ('ubuntu', 'katrain-cron'),
    'old-prod': ('10-60-219-118', 'katrain-ucloud-katrain-cron-1'),
    'new-stage': ('10-60-162-188', 'katrain-ucloud-katrain-web-1'),
    'new-prod': ('10-60-162-188', 'katrain-ucloud-katrain-web-1'),
}
CUTOVER_MARKER = Path('/var/lib/ucloud-migration-20261027/cutover-authority.private.json')
TEST_RECREATE_RECEIPT = Path('/var/lib/ucloud-migration-20261027/test-container-recreate.private.json')

class Refused(RuntimeError):
    pass

def refuse(code):
    raise Refused(code)

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def canonical_time(value):
    if isinstance(value, str):
        value = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if value.tzinfo is None:
        refuse('timezone_required')
    return value.astimezone(dt.timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')

def utcnow():
    return dt.datetime.now(dt.timezone.utc)

def require_snapshot(current, expected):
    if set(current) != set(JOBS) or set(expected) != set(JOBS):
        refuse('fixed_seven_jobs_required')
    if current != expected:
        refuse('control_changed_by_other_actor')

def validate_snapshot(rows):
    if set(rows) != set(JOBS):
        refuse('fixed_seven_jobs_required')
    for job, row in rows.items():
        if row is None:
            continue
        if set(row) != set(COLUMNS) or row['job_name'] != job or type(row['paused']) is not bool:
            refuse('invalid_control_snapshot')
        if row['changed_at'] is not None and canonical_time(row['changed_at']) != row['changed_at']:
            refuse('noncanonical_timestamp')

def read_rows(q, lock=False):
    q.execute('SELECT job_name,paused,reason,changed_at,changed_by FROM cron_job_controls '
              'WHERE job_name = ANY(%s) ORDER BY job_name' + (' FOR UPDATE' if lock else ''), (list(JOBS),))
    result = {job: None for job in JOBS}
    for raw in q.fetchall():
        row = dict(zip(COLUMNS, raw))
        if row['changed_at'] is not None:
            row['changed_at'] = canonical_time(row['changed_at'])
        result[row['job_name']] = row
    validate_snapshot(result)
    return result

def db_connect():
    logging.disable(logging.CRITICAL)
    from sqlalchemy import create_engine
    from sqlalchemy.pool import NullPool
    url = os.environ.get('CRON_DATABASE_URL') or os.environ.get('KATRAIN_DATABASE_URL')
    if not url:
        from katrain.cron.config import DATABASE_URL
        url = DATABASE_URL
    engine = create_engine(url, echo=False, poolclass=NullPool)
    if engine.dialect.name != 'postgresql':
        refuse('postgresql_required')
    return engine.raw_connection()

def db_worker(payload):
    mode = payload.get('mode')
    if mode not in ('read', 'pause', 'restore'):
        refuse('unsupported_worker_mode')
    c = db_connect()
    try:
        q = c.cursor()
        if mode == 'read':
            q.execute('SET TRANSACTION READ ONLY')
        q.execute("SET LOCAL statement_timeout='8s'")
        q.execute("SET LOCAL lock_timeout='3s'")
        q.execute("SET LOCAL TIME ZONE 'UTC'")
        q.execute('SELECT current_database(), inet_server_addr()::text, inet_server_port(), current_timestamp')
        database, address, port, timestamp = q.fetchone()
        authority = {'database': database, 'server_address': address, 'server_port': port}
        if database != payload['expected_database']:
            refuse('database_name_mismatch')
        if mode == 'read':
            result = {'authority': authority, 'rows': read_rows(q), 'timestamp': canonical_time(timestamp)}
            c.rollback()
            return result
        if payload.get('go') != 'APPROVED:' + payload['window_id']:
            refuse('exact_controller_go_required')
        # Host persisted this complete before+after plan before worker invocation.
        if authority != payload['expected_authority']:
            refuse('database_authority_mismatch')
        deadline = dt.datetime.fromisoformat(payload['deadline'].replace('Z', '+00:00'))
        if utcnow() >= deadline and not (mode == 'restore' and payload.get('ack_expired') is True):
            refuse('window_expired_pause_preserved')
        before, paused = payload['before'], payload['paused']
        validate_snapshot(before)
        validate_snapshot(paused)
        expected = before if mode == 'pause' else paused
        target = paused if mode == 'pause' else before
        current = read_rows(q, lock=True)
        require_snapshot(current, expected)
        for job in JOBS:
            wanted = target[job]
            if wanted is None:
                # Exact current image was locked and checked against this window above.
                q.execute('DELETE FROM cron_job_controls WHERE job_name=%s', (job,))
                if q.rowcount != 1:
                    refuse('control_delete_raced')
            elif current[job] is None:
                q.execute('INSERT INTO cron_job_controls(job_name,paused,reason,changed_at,changed_by) '
                          'VALUES(%s,%s,%s,%s,%s) ON CONFLICT(job_name) DO NOTHING',
                          tuple(wanted[column] for column in COLUMNS))
                if q.rowcount != 1:
                    refuse('control_insert_raced')
            else:
                q.execute('UPDATE cron_job_controls SET paused=%s,reason=%s,changed_at=%s,changed_by=%s '
                          'WHERE job_name=%s',
                          (wanted['paused'], wanted['reason'], wanted['changed_at'], wanted['changed_by'], job))
                if q.rowcount != 1:
                    refuse('control_update_raced')
        after = read_rows(q)
        require_snapshot(after, target)
        # Missing rows can be inserted concurrently after SELECT. ON CONFLICT detects
        # that race; any detected conflict rolls back all seven mutations.
        c.commit()
        return {'committed': True, 'control_sha256': digest(after), 'rows': after}
    except BaseException:
        c.rollback()
        raise
    finally:
        c.close()

def run(args, stdin=None):
    result = subprocess.run(args, input=stdin, text=True, capture_output=True, timeout=25)
    if result.returncode:
        # Never relay Docker/SQL/config stderr: it may contain credentials or row values.
        try:
            message = json.loads(result.stdout)
            code = message.get('error_code', 'container_command_failed')
        except (ValueError, TypeError):
            code = 'container_command_failed'
        refuse(code if re.fullmatch('[a-z_]+', str(code)) else 'container_command_failed')
    return result.stdout

def host_authority(a):
    if ROLE_TARGETS[a.env_role] != (a.expected_hostname, a.container):
        refuse('env_role_target_mismatch')
    if socket.gethostname() != a.expected_hostname:
        refuse('hostname_mismatch')
    if a.container not in CONTAINERS:
        refuse('container_not_allowlisted')
    # Whitelist selected metadata; docker inspect environment never leaves this process.
    output = run(['docker', 'inspect', '--format', '{{.Id}} {{.Image}} {{.State.Running}}', a.container]).split()
    if len(output) != 3 or output[2] != 'true':
        refuse('explicit_container_not_running')
    return {'hostname': a.expected_hostname, 'env_role': a.env_role, 'container': a.container,
            'container_id': output[0], 'image_id': output[1]}

def call(a, payload):
    payload = dict(payload, expected_database=a.expected_database)
    source = Path(__file__).read_text()
    output = run(['docker', 'exec', '--user', '0:0', '-i', a.container, 'python3', '-c', source, '--worker'],
                 json.dumps(payload))
    return json.loads(output)

def open_private_directory(path):
    directory = path.parent
    directory.mkdir(mode=0o700, parents=False, exist_ok=True)
    info = directory.lstat()
    if not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o700 or info.st_uid != os.geteuid():
        refuse('private_state_directory_requires_owned_0700')
    lock = os.open(str(directory / '.operator.lock'), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    lock_info = os.fstat(lock)
    if not stat.S_ISREG(lock_info.st_mode) or stat.S_IMODE(lock_info.st_mode) != 0o600 or lock_info.st_uid != os.geteuid():
        refuse('unsafe_private_lock')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        refuse('private_state_operator_busy')
    return lock

def fsync_directory(directory):
    fd = os.open(str(directory), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)

def save_private(path, value, fresh=False):
    data = (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()
    if fresh:
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            with os.fdopen(fd, 'wb') as out:
                out.write(data)
                out.flush()
                os.fsync(out.fileno())
        finally:
            fsync_directory(path.parent)
        return
    fd, temporary = tempfile.mkstemp(prefix='.state-', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, path)
        fsync_directory(path.parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

def load_private(path):
    fd = os.open(str(path), os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'r') as source:
        info = os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600 or info.st_uid != os.geteuid():
            refuse('private_state_requires_owned_0600')
        value = json.load(source)
    return value

def require_test_recreate_identity(origin, target, receipt, window_id):
    if origin.get('env_role') != 'test' or target.get('env_role') != 'test':
        refuse('test_recreate_role_mismatch')
    if (origin.get('hostname'), origin.get('container')) != ROLE_TARGETS['test']:
        refuse('test_recreate_origin_mismatch')
    if not re.fullmatch('[0-9a-f]{64}', str(origin.get('container_id', ''))):
        refuse('test_recreate_old_id_invalid')
    if not re.fullmatch('[0-9a-f]{64}', str(target.get('container_id', ''))):
        refuse('test_recreate_new_id_invalid')
    if target['container_id'] == origin['container_id']:
        refuse('test_recreate_requires_changed_container_id')
    expected = dict(origin, container_id=target['container_id'])
    if target != expected:
        refuse('test_recreate_only_container_id_may_change')
    required = {
        'Schema': 1, 'WindowID': window_id, 'Hostname': origin['hostname'],
        'EnvRole': 'test', 'ContainerName': origin['container'],
        'OldContainerID': origin['container_id'], 'NewContainerID': target['container_id'],
        'ImageID': origin['image_id'], 'DatabaseName': origin['database']['database'],
        'DatabaseServerAddress': origin['database']['server_address'],
        'DatabaseServerPort': origin['database']['server_port'],
    }
    if any(receipt.get(key) != value or type(receipt.get(key)) is not type(value) for key, value in required.items()):
        refuse('test_recreate_receipt_mismatch')

def authorize_test_recreate(state, authority, a):
    if not a.allow_test_container_recreate or a.mode != 'restore' or a.env_role != 'test':
        refuse('explicit_test_restore_recreate_required')
    fd = os.open(str(TEST_RECREATE_RECEIPT), os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'r') as source:
        info = os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600 or info.st_uid != 0:
            refuse('test_recreate_receipt_requires_root_owned_0600')
        receipt = json.load(source)
    require_test_recreate_identity(state['origin_authority'], authority, receipt, state['window_id'])

def authorize_cross_restore(state, authority, a):
    if not a.allow_restore_target_change or a.env_role != 'new-prod':
        refuse('target_authority_changed_explicit_new_prod_restore_required')
    if state['origin_authority']['env_role'] != 'old-prod':
        refuse('cross_restore_origin_must_be_old_prod')
    # Root-owned controller marker is created only AFTER old writers are fenced
    # and the final logical data restore has been independently verified.
    fd = os.open(str(CUTOVER_MARKER), os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'r') as source:
        info = os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600 or info.st_uid != 0:
            refuse('cutover_marker_requires_root_owned_0600')
        marker = json.load(source)
    required = {
        'Schema': 1, 'WindowID': state['window_id'],
        'OldHostname': state['origin_authority']['hostname'],
        'NewHostname': authority['hostname'],
        'OldWritersFenced': True, 'FinalDataVerified': True,
        'ControlStateSHA256': state['plan_sha256'],
        'OldDatabaseName': state['origin_authority']['database']['database'],
        'NewDatabaseName': authority['database']['database'],
    }
    if any(marker.get(key) != value or type(marker.get(key)) is not type(value) for key, value in required.items()):
        refuse('cutover_authority_marker_mismatch')
    for key in ('OldFenceReceiptSHA256', 'FinalRestoreReceiptSHA256'):
        if not re.fullmatch('[0-9a-f]{64}', str(marker.get(key, ''))):
            refuse('cutover_authority_receipt_hash_required')

def ensure_plan(state, a):
    if state.get('format') != 1 or state.get('window_id') != a.window_id or state.get('owner') != a.owner:
        refuse('state_window_or_owner_mismatch')
    validate_snapshot(state['before'])
    validate_snapshot(state['paused'])
    for job in JOBS:
        row = state['paused'][job]
        if row != {'job_name': job, 'paused': True, 'reason': state['reason'],
                   'changed_at': state['paused_at'], 'changed_by': state['owner']}:
            refuse('invalid_window_paused_image')
    if digest({'before': state['before'], 'paused': state['paused']}) != state['plan_sha256']:
        refuse('private_plan_digest_mismatch')

def main():
    if sys.argv[1:] == ['--worker']:
        print(json.dumps(db_worker(json.load(sys.stdin))))
        return
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=('prepare', 'pause', 'status', 'restore'), nargs='?', default='status')
    p.add_argument('--state', type=Path, required=True)
    p.add_argument('--window-id', required=True)
    p.add_argument('--owner', required=True)
    p.add_argument('--expected-hostname', required=True)
    p.add_argument('--env-role', choices=ROLES, required=True)
    p.add_argument('--container', choices=sorted(CONTAINERS), required=True)
    p.add_argument('--expected-database', required=True)
    p.add_argument('--deadline', help='UTC RFC3339, required for prepare')
    p.add_argument('--go', default='')
    p.add_argument('--allow-restore-target-change', action='store_true',
                   help='Explicitly restore copied window image in final new-prod authority')
    p.add_argument('--ack-expired', action='store_true', help='Explicit CAS restore after deadline; never auto restore')
    p.add_argument('--allow-test-container-recreate', action='store_true',
                   help='Explicit TEST-only restore after planned same-image container recreation; root receipt required')
    a = p.parse_args()
    if not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,79}', a.window_id):
        refuse('invalid_window_id')
    if not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.:@-]{0,63}', a.owner):
        refuse('invalid_owner')
    if not a.state.is_absolute():
        refuse('absolute_private_state_path_required')
    if a.mode in ('pause', 'restore') and a.go != 'APPROVED:' + a.window_id:
        refuse('exact_controller_go_required')
    if a.allow_test_container_recreate and (a.mode != 'restore' or a.env_role != 'test' or a.allow_restore_target_change):
        refuse('test_recreate_restore_only_no_cross_authority_option')
    if (a.allow_restore_target_change or a.ack_expired) and a.mode != 'restore':
        refuse('restore_only_option')
    lock = open_private_directory(a.state)
    try:
        host = host_authority(a)
        current = call(a, {'mode': 'read'})
        authority = dict(host, database=current['authority'])
        if a.mode == 'prepare':
            if a.allow_restore_target_change or a.ack_expired or not a.deadline:
                refuse('explicit_prepare_deadline_required')
            deadline = canonical_time(a.deadline)
            if not utcnow() < dt.datetime.fromisoformat(deadline.replace('Z', '+00:00')):
                refuse('prepare_deadline_expired')
            reason = 'migration:' + a.window_id + ';deadline=' + deadline
            paused = {job: {'job_name': job, 'paused': True, 'reason': reason,
                            'changed_at': current['timestamp'], 'changed_by': a.owner} for job in JOBS}
            state = {'format': 1, 'window_id': a.window_id, 'owner': a.owner, 'deadline': deadline,
                     'reason': reason, 'paused_at': current['timestamp'], 'origin_authority': authority,
                     'before': current['rows'], 'paused': paused, 'phase': 'prepared_read_only',
                     'plan_sha256': digest({'before': current['rows'], 'paused': paused})}
            save_private(a.state, state, fresh=True)
            print(json.dumps({'phase': state['phase'], 'window_id': a.window_id, 'job_count': len(JOBS),
                              'before_present_count': sum(row is not None for row in state['before'].values()),
                              'before_sha256': digest(state['before']), 'plan_sha256': state['plan_sha256']}))
            return
        state = load_private(a.state)
        ensure_plan(state, a)
        same_authority = authority == state['origin_authority']
        if same_authority and a.allow_test_container_recreate:
            refuse('test_recreate_requires_changed_container_id')
        if not same_authority and a.mode != 'status':
            if a.mode != 'restore':
                refuse('target_authority_changed_explicit_new_prod_restore_required')
            if a.allow_test_container_recreate:
                authorize_test_recreate(state, authority, a)
            else:
                authorize_cross_restore(state, authority, a)
        if a.mode == 'status':
            rows = current['rows']
            print(json.dumps({'phase': 'read_only_status', 'window_id': a.window_id,
                              'matches_before': rows == state['before'], 'matches_window_paused': rows == state['paused'],
                              'present_count': sum(row is not None for row in rows.values()),
                              'paused_count': sum(row is not None and row['paused'] is True for row in rows.values()),
                              'control_sha256': digest(rows), 'deadline': state['deadline'],
                              'matches_origin_authority': same_authority}))
            return
        if utcnow() >= dt.datetime.fromisoformat(state['deadline'].replace('Z', '+00:00')):
            if a.mode != 'restore' or not a.ack_expired:
                refuse('window_expired_pause_preserved')
        require_snapshot(current['rows'], state['before'] if a.mode == 'pause' else state['paused'])
        # Durable host before+planned-after must exist BEFORE mutation. This extra intent
        # fsync allows recovery even if commit succeeds but the caller loses its reply.
        state['last_intent'] = {'mode': a.mode, 'target_authority': authority, 'at': canonical_time(utcnow())}
        save_private(a.state, state)
        verify = load_private(a.state)
        ensure_plan(verify, a)
        if verify != state:
            refuse('private_state_persistence_mismatch')
        result = call(a, {'mode': a.mode, 'window_id': a.window_id, 'owner': a.owner,
                          'go': a.go, 'deadline': state['deadline'], 'ack_expired': a.ack_expired,
                          'expected_authority': current['authority'], 'before': state['before'], 'paused': state['paused']})
        target = state['paused'] if a.mode == 'pause' else state['before']
        require_snapshot(result['rows'], target)
        state['phase'] = 'paused' if a.mode == 'pause' else 'restored_exact_before'
        state['last_receipt'] = {'target_authority': authority, 'at': canonical_time(utcnow()),
                                 'control_sha256': result['control_sha256']}
        save_private(a.state, state)
        print(json.dumps({'phase': state['phase'], 'window_id': a.window_id,
                          'job_count': len(JOBS), 'control_sha256': result['control_sha256'],
                          'authority_changed_explicitly': not same_authority,
                          'test_container_recreated_explicitly': a.allow_test_container_recreate}))
    finally:
        os.close(lock)

if __name__ == '__main__':
    try:
        main()
    except BaseException as exc:
        code = str(exc) if isinstance(exc, Refused) and re.fullmatch('[a-z_]+', str(exc)) else 'details_redacted'
        print(json.dumps({'phase': 'refused', 'error_type': type(exc).__name__, 'error_code': code}))
        sys.exit(1)
