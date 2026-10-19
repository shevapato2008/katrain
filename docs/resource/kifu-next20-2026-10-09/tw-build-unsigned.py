"""Produce existing-gate unsigned TW anchors and finite scoped evidence."""
import datetime,gzip,hashlib,json,re,shutil,zipfile
from pathlib import Path
from katrain.web.kifu.name_evidence import registry_sha256,validate_transliteration_sources
from katrain.web.kifu.name_orthographic import VERSION,EXCLUDED_CHARACTERS,EXCLUDED_NAMES
D=Path(__file__).parent
UURL='https://www.unicode.org/Public/17.0.0/ucd/Unihan.zip'
MURL='https://ws.moe.edu.tw/001/Upload/userfiles/%E9%99%84%E8%A1%A8-%E7%B0%A1%E5%8C%96%E5%AD%97%E5%B0%8D%E7%85%A7%E6%A8%99%E6%BA%96%E5%AD%97-%E7%AD%86%E7%95%AB%E5%BA%8F.pdf'
FILES=[('/tmp/kifu-tw20-Unihan-17.0.0.zip','tw-Unihan-17.0.0.zip','f7a48b2b545acfaa77b2d607ae28747404ce02baefee16396c5d2d7a8ef34b5e'),('/tmp/kifu-tw20-moe-strokes.pdf','tw-moe-strokes.pdf','5e7173d5aa11064d3d5662d5ce4723626f2b4d2122da264f7d63e946a5815434')]
def write(n,v):(D/n).write_text(json.dumps(v,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
def pending(content):return {'content':content,'production':{'producer_id':'/root/next_batch_source_recovery','producer_model':'GPT-6; exact runtime variant unavailable','produced_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'content_sha256':registry_sha256(content)}}
def main():
 for src,name,sha in FILES:
  raw=Path(src).read_bytes();assert hashlib.sha256(raw).hexdigest()==sha;(D/name).write_bytes(raw)
 raw=zipfile.ZipFile(D/'tw-Unihan-17.0.0.zip').read('Unihan_Variants.txt');lines=raw.decode().splitlines();records={}
 for line in lines:
  if line and not line.startswith('#'):
   point,prop,value=line.split('\t');records.setdefault(chr(int(point[2:],16)),[]).append(line)
 anchors=[];manifest=[];held=[];pairs={}
 kba=json.load(gzip.open(D/'tw-kba446-actual-capture.json.gz','rt'))
 for env in ['PROD','TEST']:
  capture=json.load(gzip.open(D/f'{env}-tw-source-readonly.json.gz','rt'));members=[]
  for r in capture['rows']:
   if r['prod_id']==446:
    validate_transliteration_sources([kba],'ko',datetime.datetime.now(datetime.timezone.utc).isoformat())
    owner={'kind':'player','id':r['id']};original='李貞垠';ref='official_hanja_preserved'
    content={'reference_kind':ref,'owner':owner,'original_name':original,'source_lang':'ko','source_script':'Hanja','korean_name':'이정은','binding':{'kind':'official_person','owner':owner,'person_id_namespace':'kba_pkey','person_id':'10001264','identity_basis':kba['identity_basis']},'sources':[kba]}
   elif r['current_target']is not None:
    held.append({'environment':env,'player_id':r['id'],'prod_id':r['prod_id'],'canonical_name':r['canonical_name'],'reason':'verified_display requires physical NULL target; existing REVIEW name needs supported direct official source branch or scope change','target_preimage':r['current_target']});continue
   else:
    assert r['source_name']['lang']=='jp'and r['verified_source_live']is True
    content=r['unsigned_anchor_content'];original=content['original_name'];ref=content['reference_kind'];owner=content['owner']
    assert not set(original)&EXCLUDED_CHARACTERS and original not in EXCLUDED_NAMES
    for i,ch in enumerate(original):pairs.setdefault(ch,[]).append({'environment':env,'player_id':r['id'],'position':i})
   anchor={'environment':env,'evidence_kind':'primary_orthographic','version':1,**pending(content)};anchors.append(anchor)
   item={'environment':env,'prod_id':r['prod_id'],'player_id':r['id'],'canonical_name':r['canonical_name'],'original_name':original,'display_name':original,'reference_kind':ref,'current_target':r['current_target'],'owner_preimage':r['owner_preimage'],'source_anchor_content_sha256':registry_sha256(content),'source_evidence_id':r['source_evidence']['id'],'source_name_sha256':registry_sha256(r['source_name']),'source_evidence_sha256':registry_sha256(r['source_evidence']),'linked_games':r['games'],'source_urls':r['source_urls']};manifest.append(item);members.append(item)
  write(f'{env}-tw-unsigned-member-packet.json',{'status':'unsigned_source_ready_final_context_deferred_until_post590_pages','environment':env,'members':members,'count':len(members),'source_captured_at':capture['captured_at'],'source_capture_sha256':hashlib.sha256((D/f'{env}-tw-source-readonly.json.gz').read_bytes()).hexdigest()})
 mappings=[];scoped=[]
 for ch,examples in sorted(pairs.items(),key=lambda x:ord(x[0])):
  point=f'U+{ord(ch):04X}';allrows=records.get(ch,[]);traditional=[line for line in allrows if '\tkTraditionalVariant\t'in line]
  assert not traditional or point in traditional[0].split('\t')[2].split(),(ch,traditional)
  location=f'Unihan_Variants.txt: {point} kTraditionalVariant'if traditional else f'Unihan_Variants.txt: {point} has no kTraditionalVariant record'
  mappings.append({'input':ch,'output':ch,'normative_version':'Unicode 17.0.0 Unihan_Variants.txt','normative_url':UURL,'location':location,'human_name_applicable':True})
  scoped.append({'input':ch,'output':ch,'all_actual_variant_records':allrows,'kTraditionalVariant_record':traditional[0]if traditional else None,'absence_checked_against_complete_file':not traditional,'examples':examples,'retention_basis':'Exact codepoint retention of actual qualified Japanese personal-name source; no inferred traditional counterpart and no conventional TW publication claim.'})
 jp={'version':VERSION,'reference_kind':'verified_japanese_display','lang':'tw','source_lang':'ja','source_script':'Kanji','target_script':'Hant','target_region':'TW','mappings':mappings,'excluded_characters':sorted(EXCLUDED_CHARACTERS),'excluded_names':sorted(EXCLUDED_NAMES),'exceptions_checked':True}
 kr={'version':VERSION,'reference_kind':'official_hanja_preserved','lang':'tw','source_lang':'ko','source_script':'Hanja','target_script':'Hanja','target_region':'TW','preservation':'exact_codepoints'}
 write('tw-jp-retention-rule-request.json',{'status':'pending_independent_rule_approval',**pending(jp)})
 write('tw-official-hanja-rule-request.json',{'status':'pending_independent_rule_approval',**pending(kr)})
 write('tw-Unihan17-scoped-actual-variants.json',{'source_url':UURL,'source_zip_sha256':FILES[0][2],'source_member':'Unihan_Variants.txt','complete_member_sha256':hashlib.sha256(raw).hexdigest(),'scoped_characters':scoped,'limitations':['Finite exact Japanese original retention only; semantic variants are not conversion authority.','human_name_applicable is an unsigned finite reviewer assertion, not a Unicode publication claim.']})
 write('tw-unsigned-anchor-review-requests.json',{'status':'pending_independent_original_approval','rows':anchors})
 write('tw-unsigned-manifest.json',{'status':'10_source_ready_per_environment_7_held_review_targets','rows':manifest,'held':held,'rules':{'jp':registry_sha256(jp),'hanja':registry_sha256(kr)}})
 print('unsigned anchors',len(anchors),'ready per ENV',len(manifest)//2,'held per ENV',len(held)//2,'finite JP codepoints',len(mappings))
if __name__=='__main__':main()
