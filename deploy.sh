#!/bin/bash
# IPO Tracker 部署脚本

set -e

echo "=== IPO Tracker 部署开始 ==="

# 1. 安装依赖
echo "[1/5] 安装系统依赖..."
apt update && apt install -y python3 python3-pip python3-venv

# 2. 创建项目目录
echo "[2/5] 创建项目目录..."
mkdir -p /opt/ipo-tracker
cd /opt/ipo-tracker

# 3. 上传代码（需要手动复制或用git）
echo "[3/5] 请将代码上传到 /opt/ipo-tracker 目录"

# 4. 安装Python依赖
echo "[4/5] 安装Python依赖..."
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 5. 启动服务
echo "[5/5] 启动服务..."
deactivate
nohup /opt/ipo-tracker/venv/bin/python3 main.py > /var/log/ipo-tracker.log 2>&1 &
echo "服务已启动，访问 http://你的VPS_IP:8000"

echo "=== 部署完成 ==="