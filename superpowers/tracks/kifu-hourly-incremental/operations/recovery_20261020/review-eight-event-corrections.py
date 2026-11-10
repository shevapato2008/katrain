"""Bounded, resumable actual producer/reviewer calls using the existing daily ledger."""
import asyncio
import hashlib
import json
import re
from pathlib import Path

import httpx
from sqlalchemy import select
from katrain.cron import config
from katrain.cron.db import engine
from katrain.cron.models import CronJobControlDB
from katrain.cron.jobs.kifu_ingest import DailyTokenBudget
from katrain.kifu_ingest.names import QwenNameService, NameRejected
from katrain.kifu_ingest.staging import Stage
from katrain.kifu_ingest.catalog import validate_decision, review_content_sha256

root = Path(config.KIFU_INGEST_STAGING_DIR)
work = root / 'recovery-20261020'
curated_path = work / 'curated-event-corrections.json'
assert hashlib.sha256(curated_path.read_bytes()).hexdigest() == '31da8dd74851959cf838c35c7d8e5a21f9d5f46227622c89e1a1479e27668efb'
curated = json.loads(curated_path.read_bytes())
old_path = root / 'packages/91315699-ae8fd9d9f9f4a0bd.json'
assert hashlib.sha256(old_path.read_bytes()).hexdigest() == curated['source_manifest']['file_sha256']
old = json.loads(old_path.read_bytes())
assert [c['index'] for c in curated['corrections']] == [1, 2, 7, 8, 9, 11, 12, 13]
with engine.connect() as conn:
    ctrl = conn.execute(select(CronJobControlDB.__table__).where(CronJobControlDB.job_name == 'kifu_ingest')).mappings().one()
    assert ctrl['paused'] and ctrl['changed_by'] == 'codex-hourly-recovery-20261020'
stage = Stage(root)
ledger = DailyTokenBudget(root, config.KIFU_INGEST_MAX_TOKENS, stage._atomic)
assert config.KIFU_INGEST_MAX_TOKENS == 100000 and config.KIFU_INGEST_LLM_ENABLED
results_dir = work / 'eight-event-reviews'
results_dir.mkdir(exist_ok=True)
def save(path, obj):
    stage._atomic(path, json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2).encode())
async def audit(entry):
    await asyncio.to_thread(ledger.record_call, entry)
async def reserve(tokens):
    return await asyncio.to_thread(ledger.reserve, tokens)
async def settle(reservation, tokens):
    return await asyncio.to_thread(ledger.settle, reservation, tokens)

async def main():
    sem = asyncio.Semaphore(3)
    async with httpx.AsyncClient() as client:
        service = QwenNameService(client, config.DASHSCOPE_API_KEY, max_items=8, concurrency=3,
            max_total_tokens=100000, initial_tokens_used=ledger.spent(), audit_call=audit,
            reserve_call=reserve, settle_call=settle)
        async def one(c):
            async with sem:
                i = c['index']; previous = old['decisions'][i]
                for field in ('kind', 'key', 'sources', 'source_items', 'original_language'):
                    assert previous[field] == c[field], field
                wanted = {k:c[k] for k in ('displays', 'methods', 'original_language')}
                wanted['source_urls'] = [s['url'] for s in c['sources']]
                prompt = {'kind':c['kind'], 'key':c['key'], 'sources':c['sources'],
                    'source_items':c['source_items'], 'required_candidate':wanted,
                    'required_languages':['cn','tw','jp','ko','en'],
                    'required_digit_tokens':re.findall(r'\d+',c['key']),
                    'instruction':'Return required_candidate exactly after checking the literal source and translation. These are generated literal displays, not verified official titles. Keep the original domestic/youth/world scope and every digit. Kisei is 棋圣, not Honinbo or Meijin. 青白江 is Qingbaijiang; 扇兴 is Senko/센코; 烂柯杯 uses Lanke/란커배. 总决赛 here is a finals event with its specified stage, not automatically a single final match.',
                    'correction_reason':c['reason']}
                if i == 8:
                    prompt['literal_copy_rule'] = (
                        'The reviewed wording is deliberately fixed. Reproduce required_candidate exactly, '
                        'without synonyms or added Grand. In Japanese retain 決勝大会, never 総決勝. '
                        'In Korean retain 결선, never 총결승 or 총결선. The third-place match is within '
                        'the finals tournament. Do not improve or rewrite the fixed literal titles.'
                    )
                final = results_dir / f'{i:02d}-decision-v2.json'
                if final.exists():
                    decision = json.loads(final.read_bytes()); validate_decision(decision)
                    for field in ('displays','methods','original_language','sources','source_items'):
                        assert decision[field] == c[field]
                    print(json.dumps({'index':i,'status':'reused_actual_review'}),flush=True)
                    return decision
                produced = results_dir / f'{i:02d}-producer.json'
                if produced.exists():
                    record = json.loads(produced.read_bytes())
                    candidate, producer = record['candidate'], record['producer']
                    assert {k:candidate[k] for k in wanted} == wanted
                else:
                    for attempt in range(2):
                        candidate, producer = await service._call('producer', {**prompt,'repair_attempt':attempt})
                        save(results_dir / f'{i:02d}-producer-attempt-{attempt}.json', {'candidate':candidate,'producer':producer})
                        service._candidate(candidate,c['kind'],c['key'],c['sources'])
                        if {k:candidate[k] for k in wanted} == wanted: break
                        if attempt: raise NameRejected('producer differs from finite curated correction')
                    save(produced, {'candidate':candidate,'producer':producer})
                service._candidate(candidate,c['kind'],c['key'],c['sources'])
                decision = {k:v for k,v in previous.items() if k not in ('producer','review','cn_conversion_note')}
                decision.update({k:candidate[k] for k in ('displays','methods','original_language')})
                if 'cn_conversion_note' in candidate: decision['cn_conversion_note'] = candidate['cn_conversion_note']
                decision['producer'] = producer
                review, reviewer = await service._call('reviewer', {**prompt, 'candidate':candidate, 'proposed_decision':decision,
                    'review_instructions':'Independently check all five literal displays and metadata. Approve or reject this exact candidate, no rewriting. Return only {"decision":"approve"} or {"decision":"reject"}.'})
                save(results_dir / f'{i:02d}-review-response.json', {'review':review,'reviewer':reviewer})
                assert review == {'decision':'approve'}, f'reviewer rejected index {i}'
                assert producer['request_id'] != reviewer['request_id']
                decision['review'] = {**reviewer,'decision':'approve','content_sha256':review_content_sha256(decision)}
                validate_decision(decision); save(final,decision)
                print(json.dumps({'index':i,'status':'actual_review_approved','daily_tokens_upper_bound':ledger.spent()}),flush=True)
                return decision
        results = await asyncio.gather(*(one(c) for c in curated['corrections']), return_exceptions=True)
        failures = [{'index':c['index'],'error':type(r).__name__+': '+str(r)} for c,r in zip(curated['corrections'],results) if isinstance(r,Exception)]
        if failures:
            print(json.dumps({'failures':failures,'daily_tokens_upper_bound':ledger.spent()}),flush=True)
            raise RuntimeError('bounded event review incomplete; durable successes retained')
        save(work/'replacement-event-decisions.json',results)
        print(json.dumps({'reviewed_events':len(results),'daily_tokens_upper_bound':ledger.spent(),'path':str(work/'replacement-event-decisions.json')}),flush=True)
asyncio.run(main())
