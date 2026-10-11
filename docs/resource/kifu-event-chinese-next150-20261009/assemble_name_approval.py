"""Assemble root-reviewed pending name bundles; never creates a review signature.

Root supplies name-root-approval.json after independent review. This is an
offline file transform; SQL writes and live application are separate root work.
"""

import json
from datetime import datetime
from pathlib import Path

from katrain.web.kifu.name_candidates import canonical_sha256


D = Path(__file__).resolve().parent
if not __debug__:
    raise RuntimeError('approval assembly assertions must be enabled')


def utc(value):
    moment = datetime.fromisoformat(value.replace('Z', '+00:00'))
    assert moment.tzinfo is not None
    return moment


def main():
    request = json.loads((D / 'name-review-request-unsigned.json').read_text())
    approval = json.loads((D / 'name-root-approval.json').read_text())
    assert request['status'] == 'pending_independent_root_name_review'
    assert approval['status'] == 'approved_literal_name_review'
    assert approval['request_canonical_sha256'] == canonical_sha256(request)
    assert approval['allow_name_assembly'] is True
    assert approval['reviewer_id'] == '/root' and approval['reviewer_id'] != request['producer_id']
    assert approval['reviewer_model'] and approval['review_conclusion']
    reviewed_at = utc(approval['reviewed_at'])
    assert reviewed_at >= utc(request['produced_at'])
    outputs = {env: D / f'{env}-name-approved.json' for env in ('TEST', 'PROD')}
    assert all(not path.exists() for path in outputs.values())
    assembled = {}
    for env, path in outputs.items():
        pending = json.loads((D / f'{env}-name-pending.json').read_text())
        assert pending['status'] == 'pending_independent_name_review'
        assert canonical_sha256(pending) == request['pending_artifact_canonical_sha256'][env]
        assert pending['postowner_capture_file_sha256'] == request['postowner_capture_file_sha256'][env]
        assert pending['producer_id'] == request['producer_id']
        assert len(pending['name_bundle']['owners']) == 150
        assert len(pending['name_bundle']['candidates']) == len(pending['research_records']) == 750
        assert reviewed_at >= utc(pending['bound_at'])
        for candidate in pending['name_bundle']['candidates']:
            assert candidate['review_status'] == 'pending'
            assert candidate['producer_id'] != approval['reviewer_id']
            candidate.update({'review_status': 'approved', 'reviewer_id': approval['reviewer_id'],
                              'reviewer_model': approval['reviewer_model'],
                              'reviewed_at': approval['reviewed_at'],
                              'review_conclusion': approval['review_conclusion']})
        pending['status'] = 'root_reviewed_name_bundle'
        pending['approval'] = approval
        assembled[env] = pending
    for env, path in outputs.items():
        path.write_text(json.dumps(assembled[env], ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'status': 'root_reviewed_name_bundle',
                      'canonical_sha256': {env: canonical_sha256(value)
                                           for env, value in assembled.items()}}, ensure_ascii=False))


if __name__ == '__main__':
    main()
