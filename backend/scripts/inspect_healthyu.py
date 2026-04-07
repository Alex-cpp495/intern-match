import json, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
d = json.load(open('data/wechat_articles.json', encoding='utf-8'))
arts = [a for a in d.get('articles', []) if a.get('account','') == 'HealthyUunnc']
print(f'HealthyUunnc 文章总数: {len(arts)}')
print()
for i, a in enumerate(arts):
    title = a.get('title', '')
    pub = a.get('publish_date', '')
    c = a.get('content') or ''
    summary = a.get('summary') or ''
    has_full = len(c) > 300
    print(f"[{i+1:02d}] {title[:58]}")
    print(f"      publish_date={pub or '(无)'}  正文={len(c)}字  {'✓全文' if has_full else '✗仅摘要'}")
    if not has_full and summary:
        print(f"      摘要: {summary[:80]}")
    print()
