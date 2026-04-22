# IPO Tracker 部署指南

## 1. 环境要求
- VPS: 1核1G以上
- 系统: Ubuntu 20.04+ / Debian 11+
- 端口: 8000 (TCP)

## 2. 部署步骤

### 2.1 上传代码
```bash
# 在本地打包
cd ipo-tracker
tar -czvf ipo-tracker.tar.gz ./

# 上传到VPS (在本地终端执行)
scp ipo-tracker.tar.gz root@你的VPSIP:/root/

# SSH登录VPS
ssh root@你的VPSIP
```

### 2.2 安装依赖
```bash
# 解压
cd /root
tar -xzvf ipo-tracker.tar.gz
cd ipo-tracker

# 安装Python依赖
apt update
apt install -y python3 python3-pip python3-venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2.3 启动服务
```bash
# 后台运行
nohup /root/ipo-tracker/venv/bin/python3 main.py > /var/log/ipo-tracker.log 2>&1 &

# 检查是否启动成功
curl http://localhost:8000/
```

### 2.4 配置Nginx (可选)
```bash
apt install -y nginx

# 创建配置文件
cat > /etc/nginx/sites-available/ipo-tracker << EOF
server {
    listen 80;
    server_name _;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF

# 启用配置
ln -s /etc/nginx/sites-available/ipo-tracker /etc/nginx/sites-enabled/
nginx -t && systemctl restart nginx
```

## 3. 访问方式
- API: http://你的VPSIP:8000
- Web: http://你的VPSIP:8000/web/index.html (需将web文件夹内容复制到正确位置)

## 4. 数据更新
数据获取器在 `main.py` 的 `DataFetcher` 类中，目前返回示例数据。
需要对接真实数据源时，修改对应的 fetch 方法。

## 5. 微信小程序版
如需微信小程序，请将 web/index.html 的逻辑转换为小程序WXML/WXSS格式，
API 地址改为你的VPS地址。