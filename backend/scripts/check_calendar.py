import sys, json, os
sys.path.insert(0, r'e:\Desktop\hack\intern-match\backend')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
os.chdir(r'e:\Desktop\hack\intern-match\backend')

from dotenv import load_dotenv
load_dotenv()

from routers.calendar import collect_merged_calendar_events
evs = collect_merged_calendar_events()
wx = [e for e in evs if e.source.value == 'wechat_event']
print(f'日历总事件: {len(evs)}')
print(f'其中 wechat_event: {len(wx)} 条')
print()
for e in sorted(wx, key=lambda x: x.start_iso or ''):
    date = e.start_iso[:10] if e.start_iso else '(无日期)'
    print(f'  {date:12s}  {e.title[:50]}')
