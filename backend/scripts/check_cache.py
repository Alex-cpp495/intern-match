import json, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
d = json.load(open('data/wechat_events.json', encoding='utf-8'))
print('updated_at:', d.get('updated_at'))
print('count:', d.get('count'))
evs = d.get('events', [])
hu = [e for e in evs if e.get('account','') == 'HealthyUunnc']
print(f'HealthyUunnc 活动数: {len(hu)}')
for e in hu[:5]:
    title = e.get('title','')
    ds = e.get('date_start','')
    print(f'  {title[:40]}  date_start={ds!r}')
