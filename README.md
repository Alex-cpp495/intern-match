# 校园实习智能匹配平台

基于**五维度算法 + AI 辅助**的校园实习推荐 Web App，专为宁波诺丁汉大学学生设计。

## 功能特性

- 课程表自然语言解析（DeepSeek AI）
- 五维度匹配算法：技能匹配 / 时间适配 / 兴趣契合 / 能力水平 / 企业适配
- 实时爬取实习僧宁波岗位 + 预置 UNNC 实习数据
- AI 生成个性化推荐理由
- 雷达图可视化五维度得分
- 支持远程/兼职/全职筛选

## 快速启动

### 1. 后端

```bash
cd backend

# 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # Mac/Linux

# 安装依赖（首次约3-5分钟，需下载 sentence-transformers 模型）
pip install -r requirements.txt

# 配置 DeepSeek API Key
copy .env.example .env
# 编辑 .env，填入你的 DEEPSEEK_API_KEY

# 启动服务
uvicorn main:app --reload --port 8000
```

后端启动后访问 http://localhost:8000/docs 查看 API 文档。

### 国内网络：Hugging Face 下载超时

启动日志若出现 `huggingface.co` **ConnectTimeout**，说明本机访问官方 Hub 失败。在 `backend/.env` 中**增加一行**（任选一种）：

```env
USE_HF_MIRROR=1
```

或手动指定镜像：

```env
HF_ENDPOINT=https://hf-mirror.com
```

保存后**重启** `uvicorn`。若仍想先启动服务、稍后再拉模型，可临时加：

```env
SKIP_EMBEDDER_WARMUP=1
```

（首次调用匹配时仍会加载模型，请同样配置好镜像或可访问 Hub 的网络。）

### 2. 前端

```bash
cd frontend

npm install

npm run dev
```

访问 http://localhost:3000

## 项目结构

```
intern-match/
├── backend/
│   ├── main.py                  # FastAPI 入口
│   ├── core/
│   │   ├── matcher.py           # 五维度匹配算法（核心）
│   │   ├── embedder.py          # sentence-transformers 封装
│   │   ├── schedule_parser.py   # 课程表解析（DeepSeek）
│   │   └── explainer.py         # 推荐理由生成（DeepSeek）
│   ├── scraper/
│   │   └── shixiseng.py         # 实习僧爬虫
│   ├── routers/
│   │   ├── match.py             # POST /api/match
│   │   └── jobs.py              # GET /api/jobs
│   └── data/
│       └── unnc_jobs.json       # 预置 UNNC 岗位数据
└── frontend/
    └── app/
        ├── page.tsx             # 五步骤输入页
        └── results/page.tsx     # 匹配结果展示页
```

## 五维度算法说明

```
S_total = 0.30×D1_技能匹配 + 0.25×D2_时间适配 + 0.20×D3_兴趣契合
        + 0.15×D4_能力水平 + 0.10×D5_企业适配
```

| 维度 | 权重 | 算法 |
|------|------|------|
| D1 技能匹配 | 30% | cosine_similarity(技能向量, 岗位需求向量) |
| D2 时间适配 | 25% | 空闲小时 / 岗位要求小时，规则算法 |
| D3 兴趣契合 | 20% | 0.4×Jaccard + 0.6×语义相似度 |
| D4 能力水平 | 15% | 年级分级规则 + 项目经验加成 |
| D5 企业适配 | 10% | 规模/行业/氛围标签匹配均值 |

## 部署上线（Vercel + Render）

项目采用前后端分离部署：**前端 → Vercel**，**后端 → Render**。

### Step 1：部署后端到 Render

1. 将代码推送到 GitHub
2. 登录 [Render Dashboard](https://dashboard.render.com/)
3. 点击 **New → Blueprint**，选择你的 GitHub 仓库，Render 会自动识别 `render.yaml` 并创建服务
4. 或者手动创建 **Web Service**：
   - **Root Directory**：`backend`
   - **Runtime**：Python
   - **Build Command**：`pip install -r requirements.txt`
   - **Start Command**：`uvicorn main:app --host 0.0.0.0 --port $PORT`
5. 在 Render 的 **Environment** 中设置环境变量：

| 变量 | 值 |
|---|---|
| `DEEPSEEK_API_KEY` | 你的 DeepSeek API Key |
| `JWT_SECRET` | 一个长随机字符串（Render 可自动生成） |
| `AUTH_COOKIE_SECURE` | `1` |
| `SKIP_EMBEDDER_WARMUP` | `1`（首次部署建议开启，减少启动时间） |
| `ALLOWED_ORIGINS` | 部署后填入 Vercel 前端 URL，如 `https://your-app.vercel.app` |

6. 可选：添加 **Disk**（1GB，挂载到 `/opt/render/project/src/data`）用于持久化 SQLite 和缓存文件
7. 部署完成后记下后端 URL，形如 `https://intern-match-api.onrender.com`

### Step 2：部署前端到 Vercel

1. 登录 [Vercel Dashboard](https://vercel.com/dashboard)
2. **Import** GitHub 仓库
3. 设置 **Root Directory** 为 `frontend`
4. Framework 会自动检测为 Next.js
5. 在 **Environment Variables** 中设置：

| 变量 | 值 |
|---|---|
| `NEXT_PUBLIC_API_URL` | Step 1 中后端的 URL，如 `https://intern-match-api.onrender.com` |

6. 点击 **Deploy**

### Step 3：回填前端域名到后端

部署完成后，将 Vercel 给的前端 URL 填回 Render 后端的 `ALLOWED_ORIGINS` 环境变量：

```
ALLOWED_ORIGINS=https://your-app.vercel.app
```

如果有自定义域名，用逗号分隔：

```
ALLOWED_ORIGINS=https://your-app.vercel.app,https://your-custom-domain.com
```

### 注意事项

- **Render 免费层**会在无流量时休眠（约 15 分钟），首次访问需等待 30-60 秒冷启动
- **sentence-transformers 模型**约 400MB，首次匹配请求时才下载（`SKIP_EMBEDDER_WARMUP=1`），需要几分钟
- **SQLite 数据**如果不挂载 Disk 会在重部署时丢失（用户数据、缓存等），建议挂载 Disk 或迁移到 PostgreSQL
- **定时任务**（APScheduler）在 Render 免费层可能因休眠而不执行，前端有每日首次访问自动刷新的补偿逻辑

## API 接口

- `POST /api/match` - 主匹配接口
- `GET /api/jobs` - 获取岗位缓存
- `POST /api/jobs/refresh` - 触发爬虫刷新
- `POST /api/parse-schedule` - 课程表解析预览
