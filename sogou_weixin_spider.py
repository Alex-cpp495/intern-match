import csv
import time
import random
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote


BASE_URL = "https://weixin.sogou.com"


def build_search_url(query: str, page: int) -> str:
    """
    构造搜狗微信搜索结果页 URL
    """
    encoded_query = quote(query)
    return f"{BASE_URL}/weixin?type=2&query={encoded_query}&page={page}"


def get_headers() -> dict:
    """
    构造请求头，尽量模拟正常浏览器
    """
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    ]
    return {
        "User-Agent": random.choice(user_agents),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://weixin.sogou.com/",
        "Connection": "keep-alive",
    }


def fetch_page(session: requests.Session, query: str, page: int, timeout: int = 15) -> str:
    """
    抓取单页 HTML
    """
    url = build_search_url(query, page)
    print(f"[INFO] 正在抓取第 {page} 页: {url}")

    resp = session.get(url, headers=get_headers(), timeout=timeout)
    resp.raise_for_status()

    # 搜狗页面一般 utf-8 即可；如果乱码可尝试改为 apparent_encoding
    resp.encoding = resp.apparent_encoding or "utf-8"
    return resp.text


def parse_results(html: str) -> list[dict]:
    """
    解析一页搜索结果
    """
    soup = BeautifulSoup(html, "lxml")
    items = soup.select("ul.news-list > li")

    results = []

    for li in items:
        a_tag = li.select_one("h3 a")
        if not a_tag:
            continue

        title = a_tag.get_text(" ", strip=True)
        raw_href = a_tag.get("href", "").strip()
        full_link = urljoin(BASE_URL, raw_href)

        summary_tag = li.select_one("p.txt-info")
        account_tag = li.select_one("span.all-time-y2")

        summary = summary_tag.get_text(" ", strip=True) if summary_tag else ""
        account = account_tag.get_text(" ", strip=True) if account_tag else ""

        results.append({
            "title": title,
            "link": full_link,
            "account": account,
            "summary": summary,
        })

    return results


def save_to_csv(results: list[dict], filename: str) -> None:
    """
    保存为 CSV
    """
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["page", "title", "link", "account", "summary"])
        writer.writeheader()
        writer.writerows(results)
    print(f"[INFO] 已保存 CSV: {filename}")


def save_to_html(results: list[dict], filename: str, query: str) -> None:
    """
    保存为可点击的 HTML 页面
    """
    html_parts = [
        "<!DOCTYPE html>",
        "<html lang='zh-CN'>",
        "<head>",
        "  <meta charset='utf-8'>",
        f"  <title>{query} - 搜狗微信搜索结果</title>",
        "  <style>",
        "    body { font-family: Arial, sans-serif; line-height: 1.6; margin: 30px; }",
        "    h1 { font-size: 28px; }",
        "    .item { margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid #ddd; }",
        "    .title { font-size: 20px; font-weight: bold; margin-bottom: 8px; }",
        "    .meta { color: #666; margin-bottom: 8px; }",
        "    .summary { color: #333; }",
        "    a { text-decoration: none; color: #1a73e8; }",
        "    a:hover { text-decoration: underline; }",
        "  </style>",
        "</head>",
        "<body>",
        f"<h1>关键词：{query}</h1>",
        f"<p>共抓取 {len(results)} 条结果</p>",
    ]

    for item in results:
        title = item["title"]
        link = item["link"]
        account = item["account"]
        summary = item["summary"]
        page = item["page"]

        html_parts.extend([
            "<div class='item'>",
            f"  <div class='title'><a href='{link}' target='_blank'>{title}</a></div>",
            f"  <div class='meta'>页码：{page} | 公众号：{account}</div>",
            f"  <div class='summary'>{summary}</div>",
            f"  <div><a href='{link}' target='_blank'>{link}</a></div>",
            "</div>"
        ])

    html_parts.extend([
        "</body>",
        "</html>"
    ])

    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(html_parts))

    print(f"[INFO] 已保存 HTML: {filename}")


def crawl_sogou_weixin(query: str, max_page: int = 3, sleep_min: float = 1.0, sleep_max: float = 2.0) -> list[dict]:
    """
    主爬虫逻辑
    """
    all_results = []
    session = requests.Session()

    for page in range(1, max_page + 1):
        try:
            html = fetch_page(session, query, page)
            page_results = parse_results(html)

            if not page_results:
                print(f"[INFO] 第 {page} 页未解析到结果，停止。")
                break

            for item in page_results:
                item["page"] = page

            all_results.extend(page_results)
            print(f"[INFO] 第 {page} 页抓到 {len(page_results)} 条")

        except requests.RequestException as e:
            print(f"[ERROR] 第 {page} 页请求失败: {e}")
        except Exception as e:
            print(f"[ERROR] 第 {page} 页解析失败: {e}")

        time.sleep(random.uniform(sleep_min, sleep_max))

    return all_results


def deduplicate_results(results: list[dict]) -> list[dict]:
    """
    简单去重：按 (title, link) 去重
    """
    seen = set()
    unique_results = []

    for item in results:
        key = (item["title"], item["link"])
        if key not in seen:
            seen.add(key)
            unique_results.append(item)

    return unique_results


def main():
    query = input("请输入搜索关键词：").strip()
    if not query:
        print("关键词不能为空。")
        return

    try:
        max_page = int(input("请输入要抓取的页数（例如 3）：").strip())
    except ValueError:
        print("页数输入无效，默认抓取 3 页。")
        max_page = 3

    results = crawl_sogou_weixin(query=query, max_page=max_page)
    results = deduplicate_results(results)

    if not results:
        print("没有抓到任何结果。")
        return

    csv_filename = "sogou_weixin_results.csv"
    html_filename = "sogou_weixin_results.html"

    save_to_csv(results, csv_filename)
    save_to_html(results, html_filename, query)

    print(f"[DONE] 抓取完成，共 {len(results)} 条结果。")


if __name__ == "__main__":
    main()