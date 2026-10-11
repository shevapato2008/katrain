"""Freeze literal qualified CN7 source content and finite rules; REVIEW gate unresolved."""
import gzip,hashlib,importlib.util,json,re,zipfile
from pathlib import Path
from katrain.web.kifu.name_evidence import registry_sha256
from katrain.web.kifu.name_orthographic import VERSION,EXCLUDED_CHARACTERS,EXCLUDED_NAMES
D=Path(__file__).parent
spec=importlib.util.spec_from_file_location('twbuild',D/'tw-build-unsigned.py');M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
TARGET={600:'肖澤彬',229:'葉子萌',595:'周雨萱',385:'行泓丞',662:'朱彦臻',320:'桂詩雲',391:'王琛'}
records={}
for line in zipfile.ZipFile(D/'tw-Unihan-17.0.0.zip').read('Unihan_Variants.txt').decode().splitlines():
 if line and not line.startswith('#'):
  point,prop,value=line.split('\t');records.setdefault(chr(int(point[2:],16)),[]).append(line)
moe=Path('/tmp/kifu-tw20-moe-strokes.txt').read_text().split('\f')
anchors=[];manifest=[];pairs={};examples={}
for env in ['PROD','TEST']:
 capture=json.load(gzip.open(D/f'{env}-tw-source-readonly.json.gz','rt'))
 for r in capture['rows']:
  if r['prod_id']not in TARGET:continue
  content=r['unsigned_anchor_content'];original=content['original_name'];target=TARGET[r['prod_id']]
  assert r['current_target']['status']=='review'and r['verified_source_live']is True
  assert len(original)==len(target)and not set(original+target)&EXCLUDED_CHARACTERS
  anchors.append({'environment':env,'evidence_kind':'primary_orthographic','version':1,**M.pending(content)})
  manifest.append({'environment':env,'prod_id':r['prod_id'],'owner':content['owner'],'original_name':original,'display_name':target,'target_preimage':r['current_target'],'target_preimage_sha256':registry_sha256(r['current_target']),'source_anchor_content_sha256':registry_sha256(content),'source_qualified_product_gate':True,'verified_source_live':True,'ready_under_current_gate':False})
  for i,(a,b)in enumerate(zip(original,target)):
   assert a not in pairs or pairs[a]==b;pairs[a]=b;examples.setdefault(a,[]).append({'environment':env,'player_id':r['id'],'position':i})
mappings=[];scoped=[]
for a,b in sorted(pairs.items(),key=lambda x:ord(x[0])):
 point=f'U+{ord(a):04X}';allrows=records.get(a,[]);traditional=[line for line in allrows if '\tkTraditionalVariant\t'in line]
 assert not traditional and a==b or traditional and f'U+{ord(b):04X}'in traditional[0].split('\t')[2].split(),(a,b,traditional)
 location=f'Unihan_Variants.txt: {point} kTraditionalVariant'if traditional else f'Unihan_Variants.txt: {point} has no kTraditionalVariant record'
 url=M.UURL;version='Unicode 17.0.0 Unihan_Variants.txt';locator=None
 if a!=b:
  regex=re.compile(re.escape(a)+r'\s*－\s*'+re.escape(b));matches=[(page,text.strip())for page,data in enumerate(moe,1)for text in data.splitlines()if regex.search(text)];assert len(matches)==1,(a,b,matches)
  page,text=matches[0];locator={'pdf_physical_page':page,'actual_extracted_line':text};location=f'PDF physical page {page}: {a}－{b}';url=M.MURL;version='臺灣教育部《簡化字對照標準字表》筆畫序'
 mappings.append({'input':a,'output':b,'normative_version':version,'normative_url':url,'location':location,'human_name_applicable':True})
 scoped.append({'input':a,'output':b,'all_actual_variant_records':allrows,'moe_locator':locator,'examples':examples[a]})
rule={'version':VERSION,'lang':'tw','source_lang':'zh-Hans','source_script':'Hans','target_script':'Hant','target_region':'TW','mappings':mappings,'excluded_characters':sorted(EXCLUDED_CHARACTERS),'excluded_names':sorted(EXCLUDED_NAMES),'exceptions_checked':True}
M.write('tw-cn7-pending-gate-anchor-review-requests.json',{'status':'sources_valid_but_target_REVIEW_gate_unresolved','rows':anchors})
M.write('tw-cn7-pending-gate-manifest.json',{'status':'NOT_ready_under_current_NULL_only_gate','rows':manifest,'rule_sha256':registry_sha256(rule),'notes':['P662 retained 彦 exactly; Unihan17 kTraditionalVariant includes self U+5F66 alongside U+5F65. No conventional Taiwanese spelling claim.','No SQL or source rewriting; all seven existing REVIEW row bytes preserved as actual preimages.']})
M.write('tw-cn7-finite-rule-request.json',{'status':'unsigned_pending_independent_rule_approval_and_REVIEW_gate_decision',**M.pending(rule)})
M.write('tw-cn7-scoped-actual-variants.json',{'source_url':M.UURL,'source_zip_sha256':M.FILES[0][2],'moe_source_url':M.MURL,'moe_source_sha256':M.FILES[1][2],'scoped_characters':scoped})
print('CN7 source anchors',len(anchors),'finite mappings',len(mappings),'changed',sum(a!=b for a,b in pairs.items()),'CURRENT GATE NOT READY')
