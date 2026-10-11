import hashlib, json, unicodedata
from urllib.parse import quote_plus
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
live=json.loads((ROOT/'tmp/player-next-unanchored-live.json').read_text())
prod=live['prod']['doc']; test=live['test']['doc']
excluded=set(prod['excluded_inputs']['top20'])|set(prod['excluded_inputs']['safe6'])|set(prod['excluded_inputs']['holds'])

urls={
 '姜勋':'https://zh.wikipedia.org/w/index.php?search=%E5%A7%9C%E5%8B%8B',
 'Iwamoto Kaoru':'https://en.wikipedia.org/wiki/Iwamoto_Kaoru',
 'Maeda Nobuaki':'https://ja.wikipedia.org/w/index.php?search=%E5%89%8D%E7%94%B0%E9%99%B8%E5%BF%8D',
 '林彦丞':'https://zh.wikipedia.org/w/index.php?search=%E6%9E%97%E5%BD%A6%E4%B8%9E',
 '王尧':'https://zh.wikipedia.org/w/index.php?search=%E7%8E%8B%E5%B0%A7+%E5%9B%B4%E6%A3%8B',
 'Fujisawa Hosai':'https://en.wikipedia.org/w/index.php?search=Fujisawa+Hosai',
 '蔡竞':'https://zh.wikipedia.org/wiki/%E8%94%A1%E7%AB%9E',
 'Yoshida Yoichi':'https://ja.wikipedia.org/w/index.php?search=%E5%90%89%E7%94%B0%E9%99%BD%E4%B8%80+%E5%9B%B2%E7%A2%81',
 'Ito Tomoe':'https://ja.wikipedia.org/w/index.php?search=%E4%BC%8A%E8%97%A4%E6%99%BA%E6%81%B5%E5%AD%90+%E5%9B%B2%E7%A2%81',
 '杨一':'https://zh.wikipedia.org/w/index.php?search=%E6%9D%A8%E4%B8%80+%E5%9B%B4%E6%A3%8B',
 'Okubo Ichigen':'https://ja.wikipedia.org/w/index.php?search=%E5%A4%A7%E4%B9%85%E4%BF%9D%E4%B8%80%E6%BA%90+%E5%9B%B2%E7%A2%81',
 '尹灿熙':'https://zh.wikipedia.org/w/index.php?search=%E5%B0%B9%E7%81%BF%E7%86%99+%E5%9B%B4%E6%A3%8B',
 'Kano Yoshinori':'https://ja.wikipedia.org/w/index.php?search=%E5%8A%A0%E7%B4%8D%E5%98%89%E5%BE%B3+%E5%9B%B2%E7%A2%81',
 'Iwata Tatsuaki':'https://ja.wikipedia.org/w/index.php?search=%E5%B2%A9%E7%94%B0%E9%81%94%E6%98%8E+%E5%9B%B2%E7%A2%81',
 'Sumino Tsunehiro':'https://ja.wikipedia.org/w/index.php?search=%E8%A7%92%E9%87%8E%E9%9A%86%E5%8D%9A+%E5%9B%B2%E7%A2%81',
 'Kodama Kunio':'https://ja.wikipedia.org/w/index.php?search=%E5%85%90%E7%8E%89%E5%9B%BD%E9%9B%84+%E5%9B%B2%E7%A2%81',
 'Takemiya Masaki':'https://en.wikipedia.org/wiki/Masaki_Takemiya',
 'Takahashi Toshimitsu':'https://ja.wikipedia.org/w/index.php?search=%E9%AB%98%E6%A9%8B%E4%BF%8A%E5%85%89+%E5%9B%B2%E7%A2%81',
 'Tsujii Ryotaro':'https://ja.wikipedia.org/w/index.php?search=%E8%BE%BB%E4%BA%95%E8%89%AF%E5%A4%AA%E9%83%8E+%E5%9B%B2%E7%A2%81',
 '仓桥正行':'https://ja.wikipedia.org/w/index.php?search=%E5%80%89%E6%A9%8B%E6%AD%A3%E8%A1%8C+%E5%9B%B2%E7%A2%81',
 '付冲':'https://zh.wikipedia.org/w/index.php?search=%E4%BB%98%E5%86%B2+%E5%9B%B4%E6%A3%8B',
 'Takagawa Shukaku':'https://en.wikipedia.org/wiki/Takagawa_Shukaku',
 'Tsuchiya Shuwa':'https://ja.wikipedia.org/w/index.php?search=%E5%9C%9F%E5%B1%8B%E7%A7%80%E5%92%8C+%E5%9B%B2%E7%A2%81',
 'Kobayashi Koichi':'https://en.wikipedia.org/wiki/Koichi_Kobayashi_(Go_player)',
 '陈锋':'https://zh.wikipedia.org/w/index.php?search=%E9%99%88%E9%94%8B+%E5%9B%B4%E6%A3%8B',
 '杨孟允':'https://zh.wikipedia.org/w/index.php?search=%E6%9D%A8%E5%AD%9F%E5%85%81+%E5%9B%B4%E6%A3%8B',
 'Sakai Takeshi':'https://ja.wikipedia.org/w/index.php?search=%E9%85%92%E4%BA%95%E7%8C%9B+%E5%9B%B2%E7%A2%81',
 'Honinbo Shuei':'https://en.wikipedia.org/wiki/Honinbo_Shuei',
 'Kobayashi Reiko':'https://ja.wikipedia.org/w/index.php?search=%E5%B0%8F%E6%9E%97%E7%A4%BC%E5%AD%90+%E5%9B%B2%E7%A2%81',
 'Murase Yakichi':'https://ja.wikipedia.org/w/index.php?search=%E6%9D%91%E7%80%AC%E5%BC%A5%E5%90%89+%E5%9B%B2%E7%A2%81',
}
canonical={
 'Iwamoto Kaoru':'岩本薫','Maeda Nobuaki':'前田陸仁','Fujisawa Hosai':'藤沢朋斎','Yoshida Yoichi':'吉田陽一','Ito Tomoe':'伊藤友恵','Okubo Ichigen':'大久保一元','Kano Yoshinori':'加納嘉徳','Iwata Tatsuaki':'岩田達明','Sumino Tsunehiro':'角野隆博','Kodama Kunio':'児玉国雄','Takemiya Masaki':'武宮正樹','Takahashi Toshimitsu':'高橋俊光','Tsujii Ryotaro':'辻井良太郎','Takagawa Shukaku':'高川格','Tsuchiya Shuwa':'土屋秀和','Kobayashi Koichi':'小林光一','Sakai Takeshi':'酒井猛','Honinbo Shuei':'本因坊秀栄','Kobayashi Reiko':'小林禮子','Murase Yakichi':'村瀬弥吉'}
def key(v):return ''.join(c for c in unicodedata.normalize('NFKC',v).casefold() if not c.isspace() and not unicodedata.category(c).startswith('P'))
pt={x['raw']:x for x in prod['candidates'] if x['raw'] not in excluded} 
pt=dict(list(pt.items())[:30]); tt={x['raw']:x for x in test['candidates']}
entries=[]
for rank,(raw,p) in enumerate(pt.items(),1):
    t=tt[raw]
    source_url=urls.get(raw,'https://en.wikipedia.org/w/index.php?search='+quote_plus(raw+' Go player'))
    entries.append({'rank':rank,'raw':raw,'prod_null_slots':p['slots'],'test_null_slots':t['slots'],'normalized_key':key(raw),'proposed_chinese_canonical':canonical.get(raw,raw),'variants':[raw] + ([canonical[raw]] if raw in canonical else []),'source_urls':[source_url],'prod_exact_catalog_owner_ids':[],'test_exact_catalog_owner_ids':[],'likely_existing_catalog_owner_aliases':{'test':[],'prod':[]},'potential_duplicate_ids':[], 'status':'RESEARCH_LEAD_UNANCHORED','hold_ambiguity':'HOLD until source page/person identity and per-slot SGF era/opponent checks confirm; name alone is insufficient','research_note':'No NFKC/case/punctuation-normalized exact match in either live catalog snapshot.'})
    if raw == '杨一':
        entry=entries[-1]
        entry['likely_existing_catalog_owner_aliases']={'test':[{'player_id':10215,'canonical_name':'小杨一'}],'prod':[{'player_id':4424,'canonical_name':'小杨一'}]}
        entry['potential_duplicate_ids']=[10215,4424]
        entry['research_note']='No exact normalized anchor; fuzzy Chinese alias 小杨一 exists in both catalogs and requires explicit duplicate review.'
safe_raw=[x['raw'] for x in entries[:8]]
safe={}
for env,d in [('test',test),('prod',prod)]:
    safe[env]={'raws':safe_raw,'slots':[x for x in d['safe_subset_slots'] if x['raw'] in safe_raw],'sources':d['safe_subset_sources'],'sgf_preimages':d['safe_subset_sgf_preimages']}
out={'format':'kifu-player-next-unanchored-readonly-package-v1','generated_utc':'2026-10-04','read_only':True,'scope':'Next 30 highest-frequency readable_unlinked raw names after top20/safe6/HOLD exclusions; exact normalized catalog anchors excluded in both environments. Research leads only; no identity decision and no writes.','selection_policy':{'excluded':prod['excluded_inputs'],'top_count':30,'candidate_total_null_slots_prod':sum(x['prod_null_slots'] for x in entries),'candidate_total_null_slots_test':sum(x['test_null_slots'] for x in entries)},'entries':entries,'safe_capture_subset':safe,'live_snapshot_sha256':{'test':live['test']['sha256'],'prod':live['prod']['sha256']},'source_discovery_policy':'Wikimedia/Wikipedia discovery URLs are leads; verify official Nihon Ki-in/Kansai Ki-in/KBA/CWA records before any future FK plan.'}
raw=json.dumps(out,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode(); path=ROOT/'docs/resource/kifu-player-next-unanchored-30-readonly-2026-10-04.json'; path.write_bytes(raw); (path.with_suffix(path.suffix+'.sha256')).write_text(hashlib.sha256(raw).hexdigest()+'  '+path.name+'\n')
md=['# Next 30 unanchored player NULL slots (read-only)','',f'- JSON SHA-256: `{hashlib.sha256(raw).hexdigest()}`','- Captured from live TEST and PROD repeatable-read, read-only transactions.','- No writes, identity decisions, or FK approvals.','- Excluded top20 exact-anchor group, safe6 identities, and prior HOLD raw values.','- Every entry has no exact NFKC/case/punctuation-normalized catalog owner in both snapshots.','', '|#|Raw|PROD NULL|TEST NULL|Candidate Chinese|Source lead|Potential duplicate IDs|HOLD|','|---:|---|---:|---:|---|---|---|---|']
for e in entries:
    dup=','.join(map(str,e['potential_duplicate_ids'])) or 'none'
    md.append(f"|{e['rank']}|`{e['raw']}`|{e['prod_null_slots']}|{e['test_null_slots']}|{e['proposed_chinese_canonical']}|{e['source_urls'][0]}|{dup}|yes — exact SGF/person review required|")
md += ['', '## Conservative preimage subset', '', 'The first eight rows have exact TEST and PROD album IDs, sides, full album rows, SGF content hashes, and source rows in the JSON for independent Astra review. These are captured preimages only.']
(ROOT/'docs/resource/kifu-player-next-unanchored-30-readonly-2026-10-04.md').write_text('\n'.join(md)+'\n')
print(json.dumps({'json_sha256':hashlib.sha256(raw).hexdigest(),'entries':len(entries),'safe_raws':safe_raw},ensure_ascii=False))
