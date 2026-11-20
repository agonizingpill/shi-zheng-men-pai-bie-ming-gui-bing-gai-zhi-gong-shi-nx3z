def canonical_map(entrances,redirects):
 '''现行归址：只沿active映射逐跳解析；历史成环数据停在环内，不为计算或查询抛错。'''
 mapping={x['source_id']:x['target_id'] for x in redirects if x.get('state')=='active'}
 def root(i):
  chain=[i];cur=i
  while cur in mapping and mapping[cur] not in chain:
   cur=mapping[cur];chain.append(cur)
  return cur
 return {e['id']:root(e['id']) for e in entrances}
