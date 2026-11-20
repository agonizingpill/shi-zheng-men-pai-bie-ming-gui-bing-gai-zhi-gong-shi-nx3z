import os,time,pathlib,logging
import redis
from .database import Session
from .models import MatchRun,Entrance,Alias,Candidate,Redirect
from .common import lock,rows,dump
from .matching import match
q=redis.from_url(os.environ['REDIS_URL'],decode_responses=True)
CANDIDATE_FIELDS=('source_id','target_id','similarity','conflict','source_canonical_id','target_canonical_id','source_alias_id','target_alias_id','source_alias_text','target_alias_text')
while True:
 pathlib.Path('/artifacts/address-heartbeat').write_text(str(time.time()))
 item=q.blpop('address:matching',timeout=2)
 if not item:continue
 with Session() as s:
  lock(s);run=s.get(MatchRun,int(item[1]))
  if not run or run.state!='queued':continue
  try:
   result=match([dump(x) for x in rows(s,Entrance)],[dump(x) for x in rows(s,Alias)],[dump(x) for x in rows(s,Redirect)])
   for d in result['candidates']:s.add(Candidate(run_id=run.id,**{k:d[k] for k in CANDIDATE_FIELDS}))
   run.result=result
   run.state='ready'
  except Exception as e:run.state='failed';run.error=str(e)[:500];logging.exception('matching failed')
  s.commit()
