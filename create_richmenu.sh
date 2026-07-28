#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${LINE_CHANNEL_ACCESS_TOKEN:-}" ]]; then
  echo "LINE_CHANNEL_ACCESS_TOKEN を設定してください。"
  exit 1
fi

if [[ ! -f "richmenu.json" ]]; then
  echo "richmenu.json が見つかりません。"
  exit 1
fi

if [[ ! -f "richmenu.png" ]]; then
  echo "richmenu.png が見つかりません。2500x843 のPNGを配置してください。"
  exit 1
fi

echo "1) リッチメニューを作成します..."
RICHMENU_ID=$(curl -sS -X POST https://api.line.me/v2/bot/richmenu \
  -H "Authorization: Bearer ${LINE_CHANNEL_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d @richmenu.json | python3 -c 'import sys,json; print(json.load(sys.stdin)["richMenuId"])')

echo "作成完了: ${RICHMENU_ID}"
echo "2) 画像をアップロードします..."
curl -sS -X POST "https://api-data.line.me/v2/bot/richmenu/${RICHMENU_ID}/content" \
  -H "Authorization: Bearer ${LINE_CHANNEL_ACCESS_TOKEN}" \
  -H "Content-Type: image/png" \
  --data-binary "@richmenu.png" > /dev/null

echo "3) デフォルトのリッチメニューに設定します..."
curl -sS -X POST "https://api.line.me/v2/bot/user/all/richmenu/${RICHMENU_ID}" \
  -H "Authorization: Bearer ${LINE_CHANNEL_ACCESS_TOKEN}" > /dev/null

echo "完了。現在のリッチメニューID: ${RICHMENU_ID}"
