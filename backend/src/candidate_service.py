from .models import Candidate,Entrance,Redirect
from .common import *
def verify(s,c):
 '''立案前按当前注册簿复核候选：失效或归址已变化的候选不得作为立案依据。'''
 if c.state!='valid':fail('候选因归址变化已失效，请重算后再立案')
 if c.conflict:fail('道路或门牌数字冲突，不得归并')
 canon=canonical_map([dump(x) for x in rows(s,Entrance)],[dump(x) for x in rows(s,Redirect)])
 if canon.get(c.source_id)!=c.source_canonical_id or canon.get(c.target_id)!=c.target_canonical_id:
  c.state='stale';c.stale_reason='归址已变化，重算前不可立案';s.flush()
  fail('候选因归址变化已失效，请重算后再立案')
 return c
def invalidate(s):
 '''生效或回滚改变归址后：只让端点归址真的变了的候选失效，其余照常可用。'''
 canon=canonical_map([dump(x) for x in rows(s,Entrance)],[dump(x) for x in rows(s,Redirect)])
 changed=0
 for c in rows(s,Candidate):
  if c.state!='valid':continue
  if canon.get(c.source_id)!=c.source_canonical_id or canon.get(c.target_id)!=c.target_canonical_id:
   c.state='stale';c.stale_reason='公示生效或回滚导致归址变化，请重算';changed+=1
 return changed
