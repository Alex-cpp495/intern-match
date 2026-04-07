# NottFind - UNNC 实习与校园一站平台

基于**五维度匹配算法 + DeepSeek AI** 的校园实习推荐与活动聚合 Web App，专为宁波诺丁汉大学（UNNC）学生与学生活动处设计。

## 功能概览

### 学生端
- **AI 对话式画像采集**：通过自然语言对话收集专业、技能、兴趣、时间偏好
- **五维度实习匹配**：技能匹配 / 时间适配 / 兴趣契合 / 能力水平 / 企业适配，雷达图可视化
- **校园活动日历**：聚合 UNNC 官网活动、Careers 讲座 / 宣讲会 / 招聘会、微信公众号活动
- **微信公众号聚合**：自动抓取搜狗微信搜索结果，解析正文与发布日期
- **智能日历 Agent**：AI 辅助的活动筛选与日程规划
- **课表导入**：支持 iCal (.ics) 格式导入，与活动日历合并展示
- **日历导出**：合并日历支持 .ics 下载，可导入到手机/电脑日历应用
- **个人中心**：画像管理、匹配记录、收藏岗位

### 管理功能（当前通过 API / 前端面板）
- 自定义微信公众号搜索关键词（增删改）
- 手动触发数据刷新（活动 / 文章 / 岗位）
- 自建校园活动（前端日历页内嵌面板）

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Next.js 14, React, TypeScript, Tailwind CSS, Framer Motion |
| 后端 | FastAPI, Python 3.11+, Uvicorn |
| 数据库 | SQLite（默认）/ PostgreSQL（生产推荐） |
| AI | DeepSeek API（对话、日程解析、推荐理由） |
| NLP | sentence-transformers（技能 / 兴趣语义匹配） |
| 定时任务 | APScheduler |
| 数据源 | 实习僧、UNNC 官网、Careers 系统、搜狗微信搜索 |

## 快速启动

### 1. 后端

```bash
cd backend

# 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # Mac/Linux

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
copy .env.example .env
# 编辑 .env，填入必要配置（见下方环境变量说明）

# 启动服务
uvicorn main:app --reload --port 8000
```

后端启动后访问 http://localhost:8000/docs 查看完整 API 文档。

### 2. 前端

```bash
cd frontend

npm install

npm run dev
```

访问 http://localhost:3000

### Hugging Face 模型下载（国内网络）

启动时若出现 `huggingface.co` **ConnectTimeout**，在 `backend/.env` 中加入：

```env
USE_HF_MIRROR=1
```

或想先启动服务、稍后再加载模型：

```env
SKIP_EMBEDDER_WARMUP=1
```

## 环境变量

复制 `backend/.env.example` 为 `backend/.env` 后按需修改：

| 变量 | 必填 | 说明 |
|------|------|------|
| `DEEPSEEK_API_KEY` | 是 | DeepSeek API 密钥，用于对话、智能日历等 AI 功能 |
| `JWT_SECRET` | 是 | JWT 签名密钥，生产环境务必改为长随机串 |
| `SOGOU_COOKIE` | 推荐 | 搜狗微信搜索的登录 Cookie，不配则匿名访问易被限速。会过期，需定期更新 |
| `AUTH_COOKIE_SECURE` | 否 | 设为 `1` 时 Cookie 带 Secure 标志（HTTPS 环境） |
| `APP_ENV` | 否 | 设为 `production` 时强制要求 `ALLOWED_ORIGINS` |
| `ALLOWED_ORIGINS` | 生产必填 | 逗号分隔的前端域名，如 `https://app.example.com` |
| `DATABASE_URL` | 否 | 数据库连接串，默认 SQLite `backend/data/app.db` |
| `SKIP_EMBEDDER_WARMUP` | 否 | 设为 `1` 跳过启动时模型预加载 |
| `USE_HF_MIRROR` | 否 | 设为 `1` 使用 HF 国内镜像 |

## 项目结构

```
intern-match/
├── backend/
│   ├── main.py                          # FastAPI 入口 + 定时任务
│   ├── core/
│   │   ├── matcher.py                   # 五维度匹配算法
│   │   ├── embedder.py                  # sentence-transformers 封装
│   │   ├── schedule_parser.py           # 课程表解析（DeepSeek）
│   │   ├── explainer.py                 # 推荐理由生成（DeepSeek）
│   │   ├── advisor.py                   # AI 对话画像采集
│   │   ├── conversation.py              # 对话会话管理
│   │   ├── campus_smart_calendar_agent.py  # 智能日历 Agent
│   │   └── security.py                  # JWT / 密码哈希
│   ├── db/
│   │   ├── database.py                  # SQLAlchemy 引擎
│   │   └── models.py                    # User 模型
│   ├── models/
│   │   ├── schemas.py                   # 匹配相关 Pydantic 模型
│   │   ├── calendar_schemas.py          # 日历相关模型
│   │   └── smart_calendar_schemas.py    # 智能日历模型
│   ├── routers/
│   │   ├── auth.py                      # 注册 / 登录 / 认证
│   │   ├── match.py                     # POST /api/match
│   │   ├── jobs.py                      # 岗位列表 / 刷新
│   │   ├── chat.py                      # AI 对话
│   │   ├── events.py                    # 校园活动 / 公众号文章
│   │   └── calendar.py                  # 合并日历 / iCal 导出
│   ├── scraper/
│   │   ├── shixiseng.py                 # 实习僧爬虫
│   │   ├── unnc_events.py               # UNNC 官网活动
│   │   ├── careers_lectures.py          # Careers 讲座
│   │   ├── careers_jobfairs.py          # Careers 招聘会
│   │   ├── careers_teachins.py          # Careers 宣讲会
│   │   ├── wechat_articles.py           # 微信公众号文章（搜狗）
│   │   ├── wechat_event_extractor.py    # 公众号活动正则提取
│   │   └── campus_refresh.py            # 校园数据统一刷新
│   └── data/                            # JSON 缓存 + SQLite 数据库
├── frontend/
│   ├── app/
│   │   ├── page.tsx                     # 首页（Hero + AI 对话）
│   │   ├── login/page.tsx               # 登录页
│   │   ├── register/page.tsx            # 注册页
│   │   ├── campus/page.tsx              # 校园动态（三 Tab）
│   │   ├── campus/smart-calendar/       # 智能日历
│   │   ├── results/page.tsx             # 匹配结果
│   │   ├── saved/page.tsx               # 收藏岗位
│   │   └── me/page.tsx                  # 个人中心
│   ├── components/
│   │   ├── SiteHeader.tsx               # 导航栏
│   │   ├── SiteFooter.tsx               # 页脚
│   │   └── campus/                      # 日历 / 文章卡片 / 面板组件
│   ├── hooks/
│   │   ├── useAuth.tsx                  # 认证状态管理
│   │   └── useSmartCalendarStore.tsx    # 智能日历状态
│   └── lib/                             # 路由 / 存储 / 工具函数
└── README.md
```

## API 接口概览

### 认证
- `POST /api/auth/register` - 注册（限 @nottingham.edu.cn）
- `POST /api/auth/login` - 登录
- `GET /api/auth/me` - 当前用户信息

### 实习匹配
- `POST /api/match` - 五维度匹配
- `POST /api/parse-schedule` - 课程表解析
- `GET /api/jobs` - 岗位列表
- `POST /api/jobs/refresh` - 刷新岗位缓存

### AI 对话
- `POST /api/chat` - 对话式画像采集
- `GET /api/chat/greeting` - 对话开场白

### 校园活动
- `GET /api/events` - UNNC 活动
- `GET /api/lectures` - Careers 讲座
- `GET /api/jobfairs` - 招聘会
- `GET /api/teachins` - 宣讲会
- `GET /api/articles` - 公众号文章
- `GET /api/wechat-events` - 公众号提取活动
- `POST /api/campus/refresh-all` - 刷新全部校园数据

### 日历
- `GET /api/calendar/merged` - 合并日历
- `GET /api/calendar/merged.ics` - iCal 导出
- `POST /api/calendar/import/ical` - iCal 导入
- `POST /api/calendar/smart-plan` - 智能日历 Agent

## 五维度匹配算法

```
S_total = 0.30 * D1_技能匹配 + 0.25 * D2_时间适配 + 0.20 * D3_兴趣契合
        + 0.15 * D4_能力水平 + 0.10 * D5_企业适配
```

| 维度 | 权重 | 算法 |
|------|------|------|
| D1 技能匹配 | 30% | cosine_similarity(技能向量, 岗位需求向量) |
| D2 时间适配 | 25% | 空闲小时 / 岗位要求小时，规则算法 |
| D3 兴趣契合 | 20% | 0.4 * Jaccard + 0.6 * 语义相似度 |
| D4 能力水平 | 15% | 年级分级规则 + 项目经验加成 |
| D5 企业适配 | 10% | 规模 / 行业 / 氛围标签匹配 |

## 部署

### Vercel + Render

**后端 (Render)**：
1. GitHub 推送后在 Render 创建 Web Service
2. Root Directory: `backend`，Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
3. 设置环境变量：`DEEPSEEK_API_KEY`, `JWT_SECRET`, `AUTH_COOKIE_SECURE=1`, `ALLOWED_ORIGINS`, `SKIP_EMBEDDER_WARMUP=1`
4. 建议挂载 Disk 到 `/opt/render/project/src/data`（持久化 SQLite + 缓存）

**前端 (Vercel)**：
1. Import GitHub 仓库，Root Directory: `frontend`
2. 设置 `NEXT_PUBLIC_API_URL` 为后端 URL
3. 部署后将 Vercel 域名回填到后端 `ALLOWED_ORIGINS`

### 注意事项
- Render 免费层无流量时休眠，首次访问需 30-60 秒冷启动
- sentence-transformers 模型约 400MB，首次匹配时下载
- 搜狗 Cookie 会过期，需定期在 `.env` 中更新 `SOGOU_COOKIE`
- 定时任务（03:00 岗位 / 04:00 校园活动）在免费层可能因休眠不执行，前端有每日首访自动刷新补偿

## 运维指南

### 搜狗 Cookie 更新
微信公众号抓取依赖搜狗微信搜索，需要有效的登录 Cookie：
1. 浏览器打开 https://weixin.sogou.com 并登录
2. F12 打开开发者工具 → Network → 刷新页面 → 点击任意请求 → 复制 Request Headers 中的 Cookie 整串
3. 粘贴到 `backend/.env` 的 `SOGOU_COOKIE=...`
4. 重启后端服务

### 手动刷新数据
- 公众号文章 + 校园活动：`POST /api/campus/refresh-all`（或前端点击刷新按钮）
- 岗位数据：`POST /api/jobs/refresh`
- 公众号文章链接修复：`POST /api/articles/repair-links`

### 查看服务状态
- 健康检查：`GET /health`
- API 文档：`GET /docs`
- 模型预加载：`GET /api/warmup`
