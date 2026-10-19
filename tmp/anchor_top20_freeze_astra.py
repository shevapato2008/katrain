"""Freeze a read-only independent decision and exact rebase evidence."""
import collections
import copy
import datetime
import json
from pathlib import Path
from anchor_top20_decide_astra import *

NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()
def write_immutable(path, obj):
    data = (json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2)+'\n').encode()
    with path.open('xb') as f: f.write(data)
    path.with_name(path.name+'.sha256').write_text(sha(path)+'  '+path.name+'\n')
    return pin(path)

# Validate and pin source files, including the Wikipedia text returned by web.run.
wiki_path=SOURCE/'wiki-murashima.web.txt'
wiki_meta={
    'key':'wiki-murashima','url':'https://ja.wikipedia.org/wiki/村島誼紀',
    'permanent_url':'https://ja.wikipedia.org/w/index.php?title=村島誼紀&oldid=110620171',
    'retrieved_date':'2026-10-04','retrieval_method':'web.run opened page, returned text saved verbatim',
    'text_path':str(wiki_path.relative_to(ROOT)),'text_sha256':sha(wiki_path),
    'publisher':'Japanese Wikipedia','supports':'Identity, original name Yoshikatsu/義勝, dates, Nihon Ki-in career and rank history.'}
metas=[]
for path in sorted(SOURCE.glob('*.meta.json')):
    meta=load(path)
    if meta['key']=='cwa-rating-list': continue # An unparameterized endpoint returned no records.
    for role in ['raw','text']:
        assert sha(ROOT/meta[role+'_path'])==meta[role+'_sha256']
    meta['metadata_file']=pin(path)
    meta['publisher']='China Weiqi Association' if meta['key'].startswith('cwa-') else 'Korea Baduk Association' if meta['key'].startswith('kba-') else 'Nihon Ki-in' if meta['key'].startswith('nihon-') else 'Kansai Ki-in'
    metas.append(meta)
metas.append(wiki_meta)
assert {v[1] for v in IDENTITIES.values()}<={r['key'] for r in metas}
manifest={'format':'kifu-player-anchor-top20-independent-source-manifest-v1','created_at_utc':NOW,'sources':metas,
          'limits':['Firecrawl HTTP 402 prevented use; primary sites were obtained with direct HTTPS and web.run fallback.',
                    'Wikipedia is a secondary source for the historical Murashima identity; association profiles support the other 19 identities.',
                    'Identity profiles and promotion records support contextual attribution, not an independent match transcript for every game.'],
          'cwa_api_provenance':pin(BASE/'kifu-player-new33-independent-sources-2026-10-04/cwa-frontend-script.js')}

# Exact rebase: one in-scope event FK changed, plus the two committed global rows.
korean_decision_path=BASE/'kifu-event-next-after-china-ahan-independent-decision-astra-2026-10-04.json'
korean_decision=load(korean_decision_path)
assert sha(korean_decision_path)=='749e066920dcdc0fc181074f15c10128e7f277ba87d98d699e87bc5638595d80'
korean_approved={r['id']:r for r in korean_decision['approved']}
assert korean_approved[70944]['family_key']=='kr_gs_caltex'
receipt=BASE/'kifu-event-korean-two-applied-2026-10-04.md'
assert sha(receipt)=='a59f0bbc5f4b5ba0e908e18073a56083e3dd743e355e0d5159571a867a76f4cf'
rebase={'format':'kifu-player-anchor-top20-exact-post-korean-rebase-astra-v1','reviewed_at_utc':NOW,'database_writes':0,
        'korean_decision':pin(korean_decision_path),'commit_receipt':pin(receipt),'environments':{}}
for env,expanded in SNAPS.items():
    original_path=BASE/f'kifu-player-exact-anchor-top20-{env}-full-preimage-astra-2026-10-04.json.gz'
    post_path=BASE/f'kifu-player-exact-anchor-top20-{env}-post-korean-full-preimage-astra-2026-10-04.json.gz'
    expanded_path=BASE/f'kifu-player-exact-anchor-top20-{env}-post-korean-expanded-full-preimage-astra-2026-10-04.json.gz'
    plan_path=BASE/f'kifu-event-korean-two-{env}-applied-plan-2026-10-04.json.gz'
    original=load(original_path);post=load(post_path);plan=load(plan_path)
    assert plan['counts']['approved']==737 and plan['database']==expanded['database']
    assert plan['decision_sha256']==sha(korean_decision_path)
    assert sha(plan_path)=={'TEST':'58ab0b967f1a1feb78d99bf9b27f63acf99f2537f3280d643aa693ba0d1d3352','PROD':'bdcda31f78fae21cd4d1087110acc2d04eef0a78d577faaf2da731a268e9d99d'}[env]
    approved_overlap=sorted(set(r['id'] for r in original['albums']) & set(korean_approved))
    assert approved_overlap==[70944]
    expected=copy.deepcopy(original)
    deltas=[]
    for label,rows in [('albums',expected['albums']),('existing_owner_context.albums',expected['existing_owner_context']['albums'])]:
        for row in rows:
            if row['id']==70944:
                assert row['event_id'] is None
                before=copy.deepcopy(row)
                assert before==next(r for r in plan['snapshot']['albums'] if r['id']==70944)
                row['event_id']=92
                deltas.append({'table_scope':label,'album_id':70944,'field':'event_id','before':None,'after':92,
                               'before_full_row_sha256':digest(before),'after_full_row_sha256':digest(row),
                               'korean_approved_record_sha256':digest(korean_approved[70944])})
    new_events=[r for r in post['events'] if r['id'] not in {x['id'] for x in original['events']}]
    assert [(r['id'],r['canonical_name']) for r in new_events]==[(92,'韩国GS加德士杯'),(93,'韩国女子国手战')]
    expected['events']+=new_events
    expected['global_counts']['event_links']+=737
    expected['captured_at_db_utc']=post['captured_at_db_utc']
    assert expected==post, 'Unexpected change in original-to-post-Korean snapshot'
    for key in post:
        if key not in ['captured_at_db_utc','variant_scan_inputs','owner_hits','existing_owner_context']:
            assert post[key]==expanded[key], (env,key)
    old_context={r['id']:r for r in post['existing_owner_context']['albums']}
    new_context={r['id']:r for r in expanded['existing_owner_context']['albums']}
    assert set(old_context)<=set(new_context)
    assert all(new_context[k]==r for k,r in old_context.items())
    assert all(r in expanded['existing_owner_context']['album_sources'] for r in post['existing_owner_context']['album_sources'])
    assert set(post['existing_owner_context']['owner_ids'])<=set(expanded['existing_owner_context']['owner_ids'])
    assert {r['id'] for r in new_context.values()}-{r['id'] for r in old_context.values()}=={r['album_id'] for r in expanded['existing_owner_context']['album_sources']}-{r['album_id'] for r in post['existing_owner_context']['album_sources']}
    rebase['environments'][env]={
        'database':expanded['database'],'original_preimage':pin(original_path),'post_korean_preimage':pin(post_path),
        'final_expanded_preimage':pin(expanded_path),'korean_applied_plan':pin(plan_path),
        'exact_event_deltas':deltas,'new_full_event_rows':new_events,
        'global_counts_before':original['global_counts'],'global_counts_after':post['global_counts'],
        'scope_unchanged':True,'all_other_original_fields_equal':True,
        'expanded_owner_ids':expanded['existing_owner_context']['owner_ids'],
        'additional_owner_ids':sorted(set(expanded['existing_owner_context']['owner_ids'])-set(post['existing_owner_context']['owner_ids'])),
        'additional_context_album_ids':sorted(set(new_context)-set(old_context)),
        'expansion_added_only_context_and_scan_metadata':True,
        'original_scope_sha256':digest(original['slots']),'final_scope_sha256':digest(expanded['slots']),
        'original_catalog_sha256':digest(original['catalog']),'final_catalog_sha256':digest(expanded['catalog'])}

rows=[inspect_slot(s) for s in SNAPS['PROD']['slots']]
slotkey=lambda r:(r['album_id'],r['side'],r['raw'])
assert len(rows)==3348 and len(set(map(slotkey,rows)))==3348
assert list(map(slotkey,SNAPS['TEST']['slots']))==list(map(slotkey,SNAPS['PROD']['slots']))
cross_environment_event_differences=[]
for aid,prod in ALBUMS['PROD'].items():
    test=ALBUMS['TEST'][aid]
    assert all(v==test[k] for k,v in prod.items() if k not in ['black_player_id','white_player_id','event_id']), (aid,'cross-environment raw album differs')
    if prod['event_id']!=test['event_id']:
        cross_environment_event_differences.append({'album_id':aid,'TEST_event_id':test['event_id'],'PROD_event_id':prod['event_id']})
assert len(cross_environment_event_differences)==65
assert all(r['PROD_event_id']==22 and r['TEST_event_id'] in [None,1] for r in cross_environment_event_differences)
assert [{k:v for k,v in r.items() if k!='created_at'} for r in SNAPS['TEST']['album_sources']]==[{k:v for k,v in r.items() if k!='created_at'} for r in SNAPS['PROD']['album_sources']]
approved=[r for r in rows if r['decision']!='HOLD'];held=[r for r in rows if r['decision']=='HOLD']
assert len(approved)==1933 and len(held)==1415
for r in rows:
    a=ALBUMS['PROD'][r['album_id']]
    r['decision_basis']='Unresolved: '+', '.join(r['reasons']) if r['reasons'] else 'Independent identity source plus unique/resolved catalogue owner, SGF/source consistency, compatible professional chronology/rank, and recorded event/opponent context.'
    if r['raw']=='李小溪05': r['identity_source_keys']+=['cwa-women-ranking','cwa-lixiaoxi-older']
    if r['raw']=='张涛': r['identity_source_keys']+=['cwa-zhangtao-homophone']
    r['root_properties_sha256']=digest(r['root_properties'])
    for env,s in SNAPS.items():
        en=r['environments'][env];target=r['target_player_id_by_environment'][env]
        assert en['before_fk'] is None
        opponent=next((p for p in s['catalog']['players'] if p['id']==en['opponent_fk']),None)
        assert en['opponent_fk'] is None or opponent is not None
        en['opponent_full_player_row']=opponent
        en['opponent_player_row_sha256']=digest(opponent)
        en['proposed_change']={r['side']+'_player_id':{'from':None,'to':target}} if target is not None else {}
        if target is not None:
            assert target!=en['opponent_fk']
            assert r['rank'] or en['opponent_fk'] is not None or (r['raw']=='李小溪05' and r['opponent_raw']=='李小溪94')
            targetrow=next(p for p in s['catalog']['players'] if p['id']==target)
            en['target_player_row_sha256']=digest(targetrow)

families=[]
for raw,info in IDENTITIES.items():
    rr=[r for r in rows if r['raw']==raw]
    family={'raw':raw,'identity_name':info[0],'birth_date':info[4],'professional_start_source_precision':info[5],
            'identity_source_keys':[info[1]],'target_player_id_by_environment':{'TEST':info[2],'PROD':info[3]},
            'candidate_count':len(rr),'approved_count':sum(r['decision']!='HOLD' for r in rr),'held_count':sum(r['decision']=='HOLD' for r in rr),
            'approved_slots':[[r['album_id'],r['side']] for r in rr if r['decision']!='HOLD'],
            'held_slots':[[r['album_id'],r['side']] for r in rr if r['decision']=='HOLD'],
            'promotion_history':TIMELINES.get(raw,[]),'environments':{}}
    if raw=='李小溪05':
        family['identity_source_keys']+=['cwa-women-ranking','cwa-lixiaoxi-older']
        family['owner_resolution']='Exact official ranking labels 05→CWA000756 (DOB2005) and94→CWA000409 (DOB1994) separate the two owners; 94 excluded, never merged.'
    elif raw=='张涛':
        family['identity_source_keys']+=['cwa-zhangtao-homophone']
        family['owner_resolution']='张涛=CWA000126 born1991, pro2004; distinct homophone张弢=CWA000460 born1993, pro2008. Chinese spelling, source-era rank, professional event/opponent context separate the owner.'
    elif info[2] is None:
        family['owner_resolution']='No survivor or target selected: multiple same-person spellings or unresolved truncated owner require a separate deduplication decision.'
    else:
        family['owner_resolution']='One owner after the explicit simplified/traditional/native/roman/former-name scan; identity attribution also requires per-slot context.'
    if raw=='辻笃仁': family['research_correction']='Kansai Ki-in gives Tsuji Shigehito, not Atsuhito. Stored names unchanged.'
    if raw=='村岛谊纪': family['research_correction']='Wikipedia gives Yoshinori, original name Yoshikatsu/義勝, not Yoshiki. Existing roman-linked owner retained; no name writes.'
    if raw=='黄宰渊': family['research_correction']='KBA gives Hwang Jaeyeon/황재연/黃宰淵; legacy English Hwang Jae-Won is not supporting evidence and is unchanged.'
    if raw=='姚智腾': family['research_correction']='Nihon Ki-in says summer2013 admission (2012 recruitment); two2012 slots remain held with the whole duplicate-owner group.'
    if raw=='河灿锡': family['promotion_note']='Pre1987 promotion sequence is not supplied; KBA history establishes professional status and national titles, and pre1987 ranks≤7 are compatible. 1987-01-01 eight-dan and2003-02-08 nine-dan boundaries use the official table.'
    if raw=='村岛谊纪': family['promotion_note']='1928 photograph/trial-game context gives four-dan before1929 five-dan. 1942 six-dan slot held against Wikipedia1943 advancement. Biography gives1954 seven-dan; no unsupported1952 substitution.'
    for env,s in SNAPS.items():
        hits=s['owner_hits'][raw];owners=sorted({h['owner_id'] for h in hits})
        owner_records=[]
        for owner in owners:
            prow=next(p for p in s['catalog']['players'] if p['id']==owner)
            linked=[]
            for a in s['existing_owner_context']['albums']:
                for side in ['black','white']:
                    if a[side+'_player_id']==owner:linked.append({'album_id':a['id'],'side':side,'raw':a['player_'+side],'date':a['date_played'],'rank':a[side+'_rank']})
            owner_records.append({'player':prow,'aliases':[p for p in s['catalog']['aliases'] if p['player_id']==owner],
                                  'names':[p for p in s['catalog']['names'] if p['player_id']==owner],
                                  'linked_slots':linked,'linked_slot_count':len(linked),'linked_raw_counts':dict(collections.Counter(p['raw'] for p in linked))})
        family['environments'][env]={'scan_inputs':s['variant_scan_inputs'][raw],'scan_hits':hits,'owner_ids':owners,'full_owner_records_and_links':owner_records}
    families.append(family)

manifest_pin=write_immutable(SOURCE/'manifest.json',manifest)
rebase_pin=write_immutable(BASE/'kifu-player-exact-anchor-top20-post-korean-exact-rebase-astra-2026-10-04.json',rebase)

decision={
 'format':'kifu-player-exact-anchor-top20-independent-decision-astra-v1','reviewed_at_utc':NOW,'review_date':'2026-10-04',
 'reviewer':'Independent Astra high-ambiguity review','status':'APPROVE_EXACT_SUBSET_HOLD_REMAINDER','database_writes':0,
 'hash_encoding':'File pins hash exact bytes. Object hashes use UTF-8 JSON, ensure_ascii=false, sort_keys=true, separators=(comma,colon). Arrays keep stated order.',
 'inputs':{'discovery':pin(BASE/'kifu-player-current-exact-anchor-candidates-2026-10-04.json'),
           'luna_research':pin(BASE/'kifu-player-exact-anchor-top20-research-2026-10-04.json'),
           'source_manifest':manifest_pin,'exact_korean_rebase':rebase_pin},
 'scope':{'raws':SNAPS['PROD']['raws'],'raw_count':20,'albums':3316,'slots':3348,'approved_slots':1933,'held_slots':1415,
          'approved_album_count':len({r['album_id'] for r in approved}),'held_album_count':len({r['album_id'] for r in held}),
          'duplicate_owner_held_slots':1313,'other_held_slots':102,'existing_context_albums_per_environment':5583},
 'scope_slots':[[r['album_id'],r['side'],r['raw']] for r in rows],
 'approved_slots':[[r['album_id'],r['side']] for r in approved],
 'held_slots':[[r['album_id'],r['side']] for r in held],
 'approved_slot_membership_sha256':digest([[r['album_id'],r['side']] for r in approved]),
 'held_slot_membership_sha256':digest([[r['album_id'],r['side']] for r in held]),
 'families':families,'approved':approved,'held':held,'environments':{},
 'source_evidence':metas,
 'cross_environment_preexisting_differences':{'scope_event_fks':cross_environment_event_differences,
    'note':'These65 pre-existing Oteai event-FK differences and environment-specific player IDs are separately preserved in complete per-environment row guards. No cross-environment reconciliation is authorized.',
    'album_source_associations':'Semantically identical; created_at differs by environment and each full timestamp is preserved/guarded.'},
 'normalization_policy':{'purpose':'Find possible owner collisions only; never grant approval from spelling alone.',
    'unicode':'NFKC, casefold, remove whitespace and Unicode punctuation',
    'han_from':'張濤韓奧紀鶴騰徹趙篤黃淵橫陳純湧燦錫勝鍾鐘島誼義昇钖',
    'han_to':'张涛韩奥纪鹤腾彻赵笃黄渊横陈纯涌灿锡胜钟钟岛谊义升锡',
    'inputs':'Exact per-family inputs in each full capture; includes native script, simplified/traditional, roman, former names and investigated truncation/homophones.',
    'limits':'Explicit scan is not proof of universal uniqueness. Known duplicated owners are held; unlisted unseen homonyms cannot be categorically excluded.'},
 'inference_policy':[
    'Association/Wikipedia sources establish identities and career chronology. Most match attribution is an inference combining those facts with the frozen SGF, source chain, event and opponent, not a claim of a separately sourced match report.',
    'Rank at a promotion date can be the previous or new grade because source dates lack the within-day change time; year/month-only dates retain their granularity. No stale-rank grace period is applied.',
    'Professional d/dan/Chinese rank tokens are interpreted in the recorded professional circuit context, not assumed to be amateur ratings.',
    'Midnight timestamp DT and date-only DT that denote the same exact day are accepted for identity chronology; original bytes and all duplicate root properties remain guarded.',
    'Second GN/EV root values can supply event context when album.event contains an old filename; all root properties and album.event remain unchanged.',
    'Missing rank is supported by a specific professional event and linked opponent; the four Li05-vs-Li94 exceptions use independent CWA exact-label identities. Missing rank plus unlinked opponent otherwise remains held.',
    'No target chosen for duplicate-owner groups, including中小野田智己/中小野田智 (the latter has9 existing links compatible with the same career).',
    'Malformed ranks, sentinel dates, unresolved chronology and missing event context remain held except the individually documented official-career cases.'
 ],
 'execution_constraints':[
    'Consume only the exact approved album_id+side memberships and environment-specific target IDs. Do not derive writes from raw-name equality, LIKE, regex, source groups or freshly expanded scope.',
    'Pin this decision, source manifest, all three generations of full capture, exact rebase and applied Korean plan/receipt byte hashes. Validate the full snapshot guards before mutation.',
    'At execution re-read the exact complete NULL-slot scope for all20 raw names, full scope albums/SGFs and source links, global player/name/alias/source/event/edition/alias catalogs, staging rows, all existing-owner context albums/source links, and global counts. Require exact preimage equality; newly appearing scope rows or owners fail closed.',
    'Only approved NULL black_player_id or white_player_id may change to the specified existing owner. No player creation, merging, deletion, alias/name edits, raw text/SGF/source/event edits, staging changes, or HOLD slot changes are authorized by this decision.',
    'Use a transaction and row locks with an exact expected change count1933 in each environment, validate expected full postimages, and roll back on any discrepancy. Shared albums with one approved and one held side change only the approved side.',
    'If another batch commits, obtain a new immutable exact rebase proving only its approved overlaps and authorized new catalog rows; never discard or weaken global catalog guards.',
    'The final expanded read-only preimage is authoritative; the earlier snapshots are retained to prove the Korean event commit and subsequent context expansion precisely.'
 ],
 'checks':{'scope_partition_complete':True,'test_prod_slot_membership_equal':True,'test_prod_raw_album_data_equal':True,
           'all_candidate_fks_null':True,'all_approved_targets_existing':True,'approved_target_not_opponent_fk':True,
           'all_source_files_hash_verified':True,'no_database_mutations_by_reviewer':True,'exact_post_korean_rebase_passed':True,
           'only_scope_rebase_delta':'album70944 event_id NULL→92','new_event_rows_only':[92,93]}}
for env,s in SNAPS.items():
    full_path=BASE/f'kifu-player-exact-anchor-top20-{env}-post-korean-expanded-full-preimage-astra-2026-10-04.json.gz'
    guard_keys=['albums','slots','album_sources','sources','events','event_editions','event_aliases','catalog','raw_staging','existing_owner_context','global_counts','owner_hits','variant_scan_inputs']
    decision['environments'][env]={'database':s['database'],'full_preimage':pin(full_path),
        'captured_at_db_utc':s['captured_at_db_utc'],'transaction_read_only':s['transaction_read_only'],'transaction_isolation':s['transaction_isolation'],
        'full_guard_sha256':{k:digest(s[k]) for k in guard_keys},
        'full_guard_counts':{k:len(s[k]) for k in ['albums','slots','album_sources','sources','events','event_editions','event_aliases','raw_staging']},
        'catalog_counts':{k:len(v) for k,v in s['catalog'].items()},'all_album_columns':sorted(s['albums'][0]),
        'scope_album_ids':[a['id'] for a in s['albums']],
        'existing_owner_context_ids':s['existing_owner_context']['owner_ids'],
        'existing_owner_context_album_ids':[a['id'] for a in s['existing_owner_context']['albums']],
        'expected_before_global_counts':s['global_counts'],
        'expected_after_global_counts':dict(s['global_counts'],player_links=s['global_counts']['player_links']+1933),
        'approved_targets_sha256':digest([[r['album_id'],r['side'],r['target_player_id_by_environment'][env]] for r in approved])}
decision['approved_records_sha256']=digest(approved);decision['held_records_sha256']=digest(held)
assert decision['inputs']['discovery']['file_sha256']=='d8ab4ddcb681d81f5c0381fa157129a009608061e343c04fd8a0cac75d55f938'
assert decision['inputs']['luna_research']['file_sha256']=='ecb362633765a45599d725773c57154ee6668845fe273e28664c4cce38d335fd'
out_path=BASE/'kifu-player-exact-anchor-top20-independent-decision-astra-2026-10-04.json'
out_pin=write_immutable(out_path,decision)
md=['# 棋手 exact-anchor top20：独立逐席决定','','2026-10-04；只读审查，数据库写入 0。',
    '', '**批准 1,933 个既有棋手 FK 关联；HOLD 1,415 个席位。** 覆盖 20 个原名、3,316 盘、3,348 个 NULL 席位。',
    '', f'决定 JSON：`{out_path.name}`；SHA-256 `{out_pin["file_sha256"]}`。',
    '', '## 逐原名结果','','| 原名 | APPROVE | HOLD | TEST / PROD 目标 ID |','|---|---:|---:|---|']
for f in families:
    ids=f['target_player_id_by_environment'];md.append(f'| {f["raw"]} | {f["approved_count"]} | {f["held_count"]} | '+(f'{ids["TEST"]} / {ids["PROD"]}' if ids['TEST'] is not None else '未选择：重复或截断条目')+' |')
md += ['', '## 关键判定', '',
 '- 七组重复或疑似截断 owner 共 1,313 席位全部保留：韩升周、奥田彩、中小野田智己、鹤田和志、姚智腾、辻笃仁、久保胜昭。中小野田智已有9条关联，年代、段位及对手与全名相符，不能任取一个 owner。',
 '- [中国围棋协会排名](https://wqapi.cwql.org.cn/playerInfo/rank/list?pageSize=1000&page=1&playerGender=2&playerStatus=1&updateCycle=202608) 将李小溪05→CWA000756、李小溪94→CWA000409；出生日期分别2005-09-06、1994-03-01。99个05席位批准，含4盘两人直接交手；不合并两个目录条目。',
 '- 张涛 [CWA000126](https://wqapi.cwql.org.cn/playerInfo/CWA000126) 与同音的张弢 [CWA000460](https://wqapi.cwql.org.cn/playerInfo/CWA000460) 出生日期、入段年份不同；逐局段位/年代/赛事支持440个席位，25个保留。',
 '- [韩国棋院黄宰渊档案](https://m.baduk.or.kr/record/gisa_info.asp?PRPL_CODE=10000686) 明确记载2011年第39期名人战综合预选战胜李世石，支持79447白方业余身份的特例。其他未经佐证的入段前棋局保留。',
 '- 更正研究中的读音依据：辻篤仁为 Shigehito；村島誼紀为 Yoshinori，旧名義勝/Yoshikatsu；黄宰渊为 Jaeyeon。此决定不修改目录姓名。',
 '- 另外102席位因年代/段位冲突、1900哨兵日期、入段前身份或赛事/对手上下文不足而保留。所有具体理由、SGF根属性、对手、来源和目标成员都在JSON逐席列出。',
 '', '## 快照与韩国赛事精确重基线', '',
 '原快照→韩国赛事提交后快照只允许本审查范围的70944赛事FK NULL→92、全局新增92/93两条赛事，以及赛事关联总数+737；其余所有字段逐字相等。随后仅扩展疑似棋手上下文，由5,561盘至5,583盘，原范围、目录及所有原上下文行不变。',
 '', f'重基线：`{Path(rebase_pin["path"]).name}`；SHA-256 `{rebase_pin["file_sha256"]}`。',
 '', '| 环境 | 最终完整快照 SHA-256 | 棋手关联前→预期后 |','|---|---|---|']
for env,e in decision['environments'].items():
    md.append(f'| {env} | `{e["full_preimage"]["file_sha256"]}` | {e["expected_before_global_counts"]["player_links"]} → {e["expected_after_global_counts"]["player_links"]} |')
md += ['', '完整快照包括26个棋局字段（含SGF）、source associations、所有player/name/alias目录、赛事/届次/别名目录、来源目录、raw staging和既有owner对局。执行前须完全匹配；任何并行提交都要另作精确重基线。',
       '', '## 证据范围与执行边界', '',
       f'独立来源清单：`{manifest_pin["path"]}`，SHA-256 `{manifest_pin["file_sha256"]}`。',
       '', '棋院/棋协档案及Wikipedia提供身份与履历；大多数逐局归属是结合冻结SGF、段位、年代、赛事、对手的推断，并非声称每盘都有外部比赛报道。缺失或冲突项单独HOLD。',
       '', '仅允许JSON明确列出的album_id+side，从NULL关联到指定既有ID。不得按原名批量扩展，不创建或合并棋手，不改姓名、别名、SGF、赛事、来源或staging。全目录守卫、HOLD席位和全量原行均须验证；当前没有执行数据库更新。', '']
md_path=out_path.with_suffix('.md')
with md_path.open('x') as f:f.write('\n'.join(md))
md_path.with_name(md_path.name+'.sha256').write_text(sha(md_path)+'  '+md_path.name+'\n')
print(json.dumps({'decision':out_pin,'markdown':pin(md_path),'rebase':rebase_pin,'manifest':manifest_pin,'scope':decision['scope']},ensure_ascii=False,indent=2))
