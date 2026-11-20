from sqlalchemy import select
from .models import Entrance,Alias,Evidence,Proposal,Objection,Notice,Candidate,Redirect
from .common import *
from .candidate_service import verify
def pair(s,a,b):
 x=get(s,Entrance,a);y=get(s,Entrance,b)
 if a==b:fail('不能归并到自身')
 if x.street!=y.street or x.number!=y.number:fail('道路或门牌数字冲突，不得归并')
 canon=canonical_map([dump(e) for e in rows(s,Entrance)],[dump(r) for r in rows(s,Redirect)])
 if canon.get(a)==canon.get(b):fail('两处入口已归入同一现行地址，不可重复归并')
 return x,y
def create(s,d):
 lock(s)
 if d.get('request_id'):
  old=s.scalars(select(Proposal).where(Proposal.request_id==d['request_id'])).first()
  if old is not None:return old,False
 c=None
 if d.get('candidate_id') is not None:
  # 同一候选已有在办或不重复立案（回执丢失的重试也走这里）；已拆分/回滚提案允许重新立案。
  old=s.scalars(select(Proposal).where(Proposal.candidate_id==d['candidate_id'],Proposal.state.in_(['draft','public','active']))).first()
  if old is not None:return old,False
  c=verify(s,get(s,Candidate,d['candidate_id']))
  d['source_id'],d['target_id']=c.source_id,c.target_id
 if d.get('source_id') is None or d.get('target_id') is None:fail('请选择候选或指定来源与目标入口')
 # 回执丢失后的重试可能不带原请求号：同一对入口已有待办提案时返回原提案，不重复立案。
 same=s.scalars(select(Proposal).where(Proposal.source_id==d['source_id'],Proposal.target_id==d['target_id'],Proposal.state.in_(['draft','public']))).first()
 if same is not None:return same,False
 pair(s,d['source_id'],d['target_id'])
 if not d.get('code'):
  base=f'P-{d["source_id"]}-{d["target_id"]}';d['code']=base;n=2
  while s.scalars(select(Proposal).where(Proposal.code==d['code'])).first():d['code']=f'{base}-{n}';n+=1
 elif s.scalars(select(Proposal).where(Proposal.code==d['code'])).first():fail('提案编号已存在，请换一个编号')
 d.setdefault('candidate_id',None)
 x=Proposal(**d);s.add(x);s.flush()
 return x,True
def object_to(s,d):
 lock(s);p=get(s,Proposal,d['proposal_id'])
 if p.state not in ['draft','public']:fail('只能在生效前提交异议')
 x=Objection(**d);s.add(x);s.flush();return x
def resolve(s,id,d):
 lock(s);x=get(s,Objection,id);p=get(s,Proposal,x.proposal_id)
 if x.state!='open' or p.state not in ['draft','public']:fail('异议已经处理或提案不可复核')
 x.state='resolved';x.decision=d['decision'];x.resolution=d['resolution']
 if x.decision=='split':
  p.state='rejected'
  for n in rows(s,Notice):
   if n.proposal_id==p.id:n.state='withdrawn'
 return x
