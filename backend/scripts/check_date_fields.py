import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

d = json.load(open(Path(__file__).parent.parent / 'data/wechat_articles.json', encoding='utf-8'))
arts = [a for a in d.get('articles', []) if a.get('account','') == 'HealthyUunnc']
print(f'共 {len(arts)} 篇，date vs publish_date 对比:')
for a in arts:
    title = a.get('title','')[:40]
    date = a.get('date', '') or ''
    pub = a.get('publish_date', '') or ''
    flag = '✗' if not date and pub else ('✓' if date else '✗✗')
    print(f"  {flag}  date={date!r:15s}  publish_date={pub!r:12s}  {title}")
