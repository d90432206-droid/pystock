#!/bin/sh

# 如果環境變數 PORT 為空（例如在本地跑），預設為 80
if [ -z "$PORT" ]; then
  export PORT=80
fi

# 如果環境變數 BACKEND_URL 是空的，則預設連到本機 Docker 網路的 backend 服務
if [ -z "$BACKEND_URL" ]; then
  export BACKEND_URL="http://backend:8001"
fi

# 替換 Nginx 設定中的 Port 與 後端網址
# 使用 | 作為分隔符號避免網址中的 / 衝突
sed -i "s|listen 80;|listen $PORT;|g" /etc/nginx/conf.d/default.conf
sed -i "s|http://host.docker.internal:8001|$BACKEND_URL|g" /etc/nginx/conf.d/default.conf

echo "Starting Nginx on port $PORT, proxying to $BACKEND_URL..."

# 啟動 Nginx
nginx -g "daemon off;"
