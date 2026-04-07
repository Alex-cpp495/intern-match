"""
深度分析 HealthyUunnc 中日期/时间提取有问题的文章，帮助决定优化方向。
"""
import json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DATA = Path(__file__).parent.parent / "data" / "wechat_articles.json"
d = json.load(open(DATA, encoding='utf-8'))
arts = {a['title']: a for a in d.get('articles', []) if a.get('account') == 'HealthyUunnc'}

# 重点检查的文章
targets = [
    "A Bite of UNNC | 2023 宁诺拾味",          # 日期应是10.22，被误识别为10月18
    "【Activity】A Bite of UNNC |  宁诺拾味",    # 时间 20:00~11:30 是报名时间
    "【Lecture】Sharpening your concentration",   # 英文月名识别的日期是否正确
    "【Activity】|Be U T台秀模特招募  Be U Recruitment",  # 4.24
]

for title in targets:
    a = arts.get(title)
    if not a:
        # 模糊匹配
        for t, v in arts.items():
            if any(k in t for k in title.split('|')):
                a = v
                title = t
                break
    if not a:
        print(f"未找到: {title}\n")
        continue

    content = (a.get('content') or '').strip()
    print(f"{'='*65}")
    print(f"标题: {title}")
    print(f"发布: {a.get('publish_date','')}")
    print(f"正文前600字:")
    print(content[:600])
    print()
