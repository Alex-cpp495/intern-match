#!/bin/bash
set -e

echo "=============================="
echo " NottFind 服务器环境一键安装"
echo "=============================="

# 1. 系统更新
echo "[1/7] 更新系统包..."
apt update && apt upgrade -y

# 2. 安装基础工具
echo "[2/7] 安装基础工具..."
apt install -y git curl wget build-essential software-properties-common

# 3. 安装 Python 3.11
echo "[3/7] 安装 Python 3.11..."
add-apt-repository -y ppa:deadsnakes/ppa
apt update
apt install -y python3.11 python3.11-venv python3.11-dev python3-pip
update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
python3 --version

# 4. 安装 Node.js 20
echo "[4/7] 安装 Node.js 20..."
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt install -y nodejs
node --version
npm --version

# 5. 安装 PM2
echo "[5/7] 安装 PM2（进程管理）..."
npm install -g pm2

# 6. 安装 PostgreSQL 15
echo "[6/7] 安装 PostgreSQL..."
apt install -y postgresql postgresql-contrib
systemctl enable postgresql
systemctl start postgresql

# 创建数据库和用户
sudo -u postgres psql -c "CREATE USER nottfind WITH PASSWORD 'nottfind2026';" 2>/dev/null || true
sudo -u postgres psql -c "CREATE DATABASE internmatch OWNER nottfind;" 2>/dev/null || true
echo "PostgreSQL 数据库已创建: internmatch (用户: nottfind)"

# 7. 安装 Nginx
echo "[7/7] 安装 Nginx..."
apt install -y nginx
systemctl enable nginx

echo ""
echo "=============================="
echo " 环境安装完成！"
echo " Python: $(python3 --version)"
echo " Node:   $(node --version)"
echo " PM2:    $(pm2 --version)"
echo " Nginx:  $(nginx -v 2>&1)"
echo "=============================="
