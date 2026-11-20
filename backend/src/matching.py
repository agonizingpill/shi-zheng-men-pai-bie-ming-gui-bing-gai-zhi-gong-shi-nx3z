import re,hashlib,json
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics import precision_score,recall_score
from sklearn.model_selection import train_test_split
from .canonical import canonical_map
NUM={'零':0,'〇':0,'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9}
def number(text):
 m=re.search(r'([0-9零〇一二三四五六七八九十]+)号',text)
 if not m:return None
 t=m.group(1)
 if t.isdigit():return int(t)
 if '十' in t:
  a,b=t.split('十');return (NUM.get(a,1) if a else 1)*10+(NUM.get(b,0) if b else 0)
 return int(''.join(str(NUM[x]) for x in t))
def normalize(text):
 n=number(text)
 return re.sub(r'([0-9零〇一二三四五六七八九十]+)号',f'{n}号',text) if n is not None else text
# Simulated labelled historical alias pairs. Split before TFIDF fit/threshold selection.
def evaluation():
 pairs=[]
 for street in ['长桥路','青石街','河滨路','新民巷','榕树街','学府路','东湖路','西堤路','南苑街','北园街','柳岸路','梅花巷']:
  pairs.extend([(street+'18号',street+'十八号',1),(street+'18号南入口',street+'十八号南门',1),(street+'18号',street+'81号',0),(street+'18号',street+'19号',0)])
 tr,te=train_test_split(list(range(len(pairs))),test_size=.25,stratify=[x[2] for x in pairs],random_state=42)
 vec=TfidfVectorizer(analyzer='char',ngram_range=(1,3));vec.fit([normalize(t) for i in tr for t in pairs[i][:2]])
 def pred(ids,threshold):
  out=[]
  for i in ids:
   a,b,_=pairs[i];v=vec.transform([normalize(a),normalize(b)]);sim=float((v[0]@v[1].T).toarray()[0,0]);out.append(int(number(a)==number(b) and sim>=threshold))
  return out
 threshold=max([.35,.45,.55,.65,.75],key=lambda z:(precision_score([pairs[i][2] for i in tr],pred(tr,z),zero_division=0)+recall_score([pairs[i][2] for i in tr],pred(tr,z),zero_division=0),z))
 y=[pairs[i][2] for i in te];pr=pred(te,threshold)
 return {'seed':42,'train_pairs':len(tr),'holdout_pairs':len(te),'train_ids':tr,'holdout_ids':te,'precision':precision_score(y,pr,zero_division=0),'recall':recall_score(y,pr,zero_division=0),'threshold':threshold,'label_source':'模拟历史别名对；不代表真实地址精度'}
def match(entrances,aliases,redirects=None):
 if len(entrances)<2 or len(aliases)<2:raise ValueError('至少两个入口和两个有文字的别名')
 redirects=redirects or []
 texts=[normalize(a['text']) for a in aliases];vec=TfidfVectorizer(analyzer='char',ngram_range=(1,3));v=vec.fit_transform(texts);sim=(v@v.T).toarray();dist=np.clip(1-sim,0,2);np.fill_diagonal(dist,0)
 labels=AgglomerativeClustering(n_clusters=None,distance_threshold=.55,metric='precomputed',linkage='average').fit_predict(dist)
 eval=evaluation();by={x['id']:x for x in entrances};canon=canonical_map(entrances,redirects)
 # 按现行归址汇集别名：已改址旧门牌的叫法算在当前正式入口名下，新入口才能与“旧门牌”的叫法匹配。
 groups={}
 for i,a in enumerate(aliases):
  c=canon.get(a['entrance_id'])
  if c is None:continue
  g=groups.setdefault(c,{'aliases':[],'members':set()});g['aliases'].append((i,a));g['members'].add(a['entrance_id'])
 pairs=[]
 roots=sorted(groups)
 for i,x in enumerate(roots):
  for y in roots[i+1:]:
   score,pi,qi=max((float(sim[p][q]),p,q) for p,_ in groups[x]['aliases'] for q,_ in groups[y]['aliases'])
   if score<.2:continue
   a,b=by[x],by[y];conflict=int(a['number']!=b['number'] or a['street']!=b['street'])
   # 目标取别名更成熟的一方（别名多者），同分取小编号；方向稳定，重算时不来回翻转。
   target,source=(x,y) if (len(groups[x]['aliases']),-x)>=(len(groups[y]['aliases']),-y) else (y,x)
   sp,tp=(pi,qi) if source==x else (qi,pi)
   pairs.append({'source_id':source,'target_id':target,'similarity':round(score,6),'conflict':conflict,
    'source_canonical_id':source,'target_canonical_id':target,
    'source_alias_id':aliases[sp]['id'],'target_alias_id':aliases[tp]['id'],
    'source_alias_text':aliases[sp]['text'],'target_alias_text':aliases[tp]['text'],
    'source_group':sorted(groups[source]['members']),'target_group':sorted(groups[target]['members'])})
 # 同址入口不互荐由分组天然保证；每处归址（来源或目标）只推荐一次，冲突项单独保留供核验。
 unique={}
 for p in pairs:
  k=(p['source_id'],p['target_id'])
  if k not in unique or p['similarity']>unique[k]['similarity']:unique[k]=p
 used=set();candidates=[]
 for p in sorted((x for x in unique.values() if not x['conflict']),key=lambda z:(-z['similarity'],z['source_id'],z['target_id'])):
  if p['source_id'] in used or p['target_id'] in used:continue
  used.add(p['source_id']);used.add(p['target_id']);candidates.append(p)
 candidates.extend({k:v for k,v in p.items() if k not in ('source_group','target_group')} for p in unique.values() if p['conflict'])
 return {'algorithm':'字符TF-IDF+AgglomerativeClustering average linkage','source_sha256':hashlib.sha256(json.dumps([entrances,aliases,redirects],ensure_ascii=False,sort_keys=True).encode()).hexdigest(),'evaluation':eval,'canonical':{str(k):v for k,v in canon.items()},'clusters':[{'alias_id':a['id'],'label':int(k)} for a,k in zip(aliases,labels)],'candidates':candidates}
