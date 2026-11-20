import os,redis
from fastapi import APIRouter,Depends,HTTPException
from .database import Session
from .models import *
from .schemas import *
from .security import current,allow
from .common import *
from . import entrance_service as entrance,proposal_service as proposal,publication_service as publication,directory_service as directory
router=APIRouter()
def change(u,action,fn,supervisor=False):
 allow(u,*(['supervisor'] if supervisor else ['operator','supervisor']))
 with Session() as s:
  x=fn(s);log(s,u,action,dump(x));s.commit();return dump(x)
@router.get('/register')
def register(u=Depends(current)):
 with Session() as s:return {name:[dump(x) for x in rows(s,cls)] for name,cls in [('entrances',Entrance),('aliases',Alias),('evidence',Evidence),('runs',MatchRun),('candidates',Candidate),('proposals',Proposal),('objections',Objection),('notices',Notice),('redirects',Redirect),('clock',Registry)]}
@router.get('/audit')
def audit(u=Depends(current)):
 with Session() as s:return [dump(x) for x in rows(s,Audit)]
@router.post('/entrances')
def ecreate(d:EntranceIn,u=Depends(current)):return change(u,'登记入口',lambda s:entrance.create_entrance(s,d.model_dump()))
@router.patch('/entrances/{id}/location')
def locate(id:int,d:LocationIn,u=Depends(current)):return change(u,'补正坐标',lambda s:entrance.locate(s,id,d.model_dump()))
@router.post('/aliases')
def aliases(d:AliasIn,u=Depends(current)):return change(u,'登记别名',lambda s:entrance.alias(s,d.model_dump()))
@router.post('/evidence')
def evidence(d:EvidenceIn,u=Depends(current)):return change(u,'登记证据',lambda s:entrance.evidence(s,d.model_dump()))
@router.post('/matches')
def matching(u=Depends(current)):
 def create(s):lock(s);x=MatchRun(state='queued');s.add(x);s.flush();return x
 d=change(u,'匹配别名',create)
 try:redis.from_url(os.environ['REDIS_URL']).rpush('address:matching',d['id'])
 except Exception:
  with Session() as s:x=s.get(MatchRun,d['id']);x.state='failed';x.error='匹配队列不可达，可重新提交';s.commit()
  fail('匹配队列不可达，可重新提交')
 return d
@router.get('/candidates/{id}')
def cverify(id:int,u=Depends(current)):
 with Session() as s:
  x=get(s,Candidate,id)
  canon=canonical_map([dump(e) for e in rows(s,Entrance)],[dump(r) for r in rows(s,Redirect)])
  return {'candidate':dump(x),'source_canonical_id':canon.get(x.source_id),'target_canonical_id':canon.get(x.target_id),'valid':x.state=='valid' and canon.get(x.source_id)==x.source_canonical_id and canon.get(x.target_id)==x.target_canonical_id}
@router.post('/proposals')
def pcreate(d:ProposalIn,u=Depends(current)):
 allow(u,'operator','supervisor')
 with Session() as s:
  try:
   x,created=proposal.create(s,d.model_dump())
  except HTTPException:
   s.commit()  # create 在抛错前只有读操作和候选失效标记，提交即保留该核验留痕
   raise
  log(s,u,'归并提案' if created else '归并提案重试',dump(x) if created else {'proposal_id':x.id,'request_id':d.request_id})
  s.commit();return {'proposal':dump(x),'duplicate':not created}
@router.post('/objections')
def ocreate(d:ObjectionIn,u=Depends(current)):return change(u,'登记异议',lambda s:proposal.object_to(s,d.model_dump()))
@router.post('/objections/{id}/resolve')
def oresolve(id:int,d:ResolveIn,u=Depends(current)):return change(u,'复核异议',lambda s:proposal.resolve(s,id,d.model_dump()),True)
@router.post('/notices')
def ncreate(d:NoticeIn,u=Depends(current)):return change(u,'发布公示',lambda s:publication.publish(s,d.model_dump()),True)
@router.post('/notices/{id}/effective')
def neffect(id:int,u=Depends(current)):return change(u,'公示生效',lambda s:publication.effective(s,id),True)
@router.post('/clock')
def clock(d:ClockIn,u=Depends(current)):return change(u,'推进演示时钟',lambda s:publication.advance(s,d.model_dump()),True)
@router.get('/directory/{id}')
def lookup(id:int,u=Depends(current)):
 with Session() as s:return directory.resolve_root(s,id)
@router.post('/redirects/{id}/rollback')
def rollback(id:int,d:ReasonIn,u=Depends(current)):return change(u,'回滚目录',lambda s:directory.rollback(s,id,d.model_dump()),True)
