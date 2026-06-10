#!/bin/bash

# 使用说明：
# 1. 将本脚本中的 example.com 替换为你的真实域名
# 2. 首次部署时，先注释掉 nginx.conf 中的 SSL 相关行，让 HTTP 80 端口正常工作
# 3. 运行 ./init-letsencrypt.sh 获取证书
# 4. 取消注释 nginx.conf 中的 SSL 配置，重启 nginx

DOMAINS=("example.com" "www.example.com")
EMAIL="your-email@example.com"
STAGING=0 # 测试时设为 1，正式申请设为 0

COMPOSE_FILE="../docker-compose.yml"
NGINX_CONTAINER="dyh-nginx"

# 创建 certbot 目录
mkdir -p ../certbot/conf ../certbot/www

# 停止 nginx 容器
docker-compose -f $COMPOSE_FILE stop nginx

# 申请证书
domain_args=""
for domain in "${DOMAINS[@]}"; do
  domain_args="$domain_args -d $domain"
done

staging_arg=""
if [ $STAGING != "0" ]; then
  staging_arg="--staging"
fi

docker run -it --rm \
  -v $(pwd)/../certbot/conf:/etc/letsencrypt \
  -v $(pwd)/../certbot/www:/var/www/certbot \
  certbot/certbot certonly \
  $staging_arg \
  --manual \
  --preferred-challenges http \
  $domain_args \
  --agree-tos \
  --no-eff-email \
  -m $EMAIL

# 启动 nginx
docker-compose -f $COMPOSE_FILE up -d nginx

echo "SSL 证书申请完成。如果成功，请取消注释 nginx.conf 中的 SSL 配置并重启 nginx。"
