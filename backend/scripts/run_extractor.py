import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from scraper.wechat_event_extractor import refresh_wechat_events_cache
events = refresh_wechat_events_cache()
hu = [e for e in events if e.get('account','') == 'HealthyUunnc']
print(f'全部活动: {len(events)} 条，HealthyUunnc: {len(hu)} 条')
print()
for e in hu:
    ds = e.get('date_start','')
    de = e.get('date_end','')
    date_str = ds if ds == de else f'{ds} ~ {de}'
    ts = e.get('time_start','')
    te = e.get('time_end','')
    time_str = f'  时间:{ts}~{te}' if ts else ''
    pat = e.get('_date_pattern','')
    title = e.get('title','')
    print(f"[{e.get('account','')}] {title[:50]}")
    print(f"  日期:{date_str or '(待定)'}  [{pat}]{time_str}")
    print(f"  简介:{e.get('description','')[:80]}")
    print()
