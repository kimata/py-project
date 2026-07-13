#!/bin/bash
# SSR サーバーと Flask API 間の内部認証用シークレットを自動生成
# 環境変数で明示的に設定されている場合はそちらを優先
if [ -z "$SSR_INTERNAL_SECRET" ]; then
    export SSR_INTERNAL_SECRET=$(head -c 32 /dev/urandom | base64)
fi

exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
