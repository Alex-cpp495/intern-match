#!/bin/bash
set -e

APP_DIR="/opt/intern-match"
SERVER_IP="114.55.166.209"

echo "=============================="
echo " NottFind 应用部署"
echo "=============================="

# 1. 创建应用目录
echo "[1/6] 准备应用目录..."
mkdir -p $APP_DIR

# 如果代码已存在则跳过（手动上传的）
if [ ! -f "$APP_DIR/backend/main.py" ]; then
    echo "请先将代码上传到 $APP_DIR"
    echo "方法：在本地电脑运行 scp 命令上传，或用 git clone"
    exit 1
fi

# 2. 后端：创建虚拟环境 + 安装依赖
echo "[2/6] 安装后端 Python 依赖..."
cd $APP_DIR/backend
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install psycopg2-binary
deactivate

# 3. 创建后端 .env
echo "[3/6] 配置后端环境变量..."
if [ ! -f "$APP_DIR/backend/.env" ]; then
    cat > $APP_DIR/backend/.env << 'ENVEOF'
# 数据库
DATABASE_URL=postgresql://nottfind:nottfind2026@localhost/internmatch

# AI API Keys
DEEPSEEK_API_KEY=sk-4b586c8cac134a27b677e5f85563497b
QWEN_API_KEY=sk-311e6d7626ba4f8ba457efd8049f621b

# JWT
JWT_SECRET=5aa7e4723c9f47c76c374c0d466deab8dfeaf9eb32994d46068f9565446d052f

# 前端地址（CORS）
ALLOWED_ORIGINS=http://114.55.166.209

# embedding 模型镜像
USE_HF_MIRROR=1

# 搜狗 Cookie（可选）
SOGOU_COOKIE=
ENVEOF
    echo ".env 已创建"
else
    echo ".env 已存在，跳过"
fi

# 4. 前端：安装依赖 + 构建
echo "[4/6] 构建前端..."
cd $APP_DIR/frontend

# 配置前端 API 地址（通过 Nginx 代理，不需要端口号）
cat > .env.local << FEEOF
NEXT_PUBLIC_API_URL=
NEXTAUTH_URL=http://$SERVER_IP
NEXTAUTH_SECRET=nottfind-secret-2026
FEEOF

npm install
npm run build

# 5. 用 PM2 启动服务
echo "[5/6] 启动服务..."
cd $APP_DIR

# 停止旧进程
pm2 delete all 2>/dev/null || true

# 启动后端
pm2 start "bash -c 'cd $APP_DIR/backend && source venv/bin/activate && uvicorn main:app --host 127.0.0.1 --port 8000'" --name backend

# 启动前端
pm2 start "bash -c 'cd $APP_DIR/frontend && npm run start -- -p 3000'" --name frontend

pm2 save
pm2 startup

# 6. 配置 Nginx
echo "[6/6] 配置 Nginx..."
cp $APP_DIR/deploy/nginx-internmatch.conf /etc/nginx/sites-available/internmatch
ln -sf /etc/nginx/sites-available/internmatch /etc/nginx/sites-enabled/internmatch
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

echo ""
echo "=============================="
echo " 部署完成！"
echo " 访问地址: http://$SERVER_IP"
echo "=============================="
echo ""
pm2 status
