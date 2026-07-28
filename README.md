# LINEリッチメニュー連動 漢方体質診断（Python最小構成）

LINE公式アカウントのリッチメニューから診断を開始し、チャット上で質問に回答して体質傾向を返すサンプルです。

## できること

- リッチメニューの「診断開始」から質問開始
- 12問の3択診断（よくある / ときどき / ほぼない）
- `気虚 / 気滞 / 血虚 / 瘀血 / 陰虚 / 水毒` の簡易判定

## ファイル構成

- `app.py`: LINE Webhookサーバー本体
- `richmenu.json`: リッチメニュー定義
- `create_richmenu.sh`: リッチメニュー作成・画像設定・全ユーザー適用
- `.env.example`: 環境変数のサンプル

## 事前準備

1. LINE Developersで Messaging API チャネルを作成
2. 以下を控える
   - `Channel secret`
   - `Channel access token (long-lived)`
3. Webhook URL を `https://<公開URL>/callback` に設定  
   例: ngrok利用時 `https://xxxx.ngrok-free.app/callback`
4. 「Webhookの利用」を有効化

## 起動手順

1. 環境変数を設定

```bash
cp .env.example .env
source .env
```

2. サーバー起動

```bash
python3 app.py
```

3. トンネル公開（任意）

```bash
# ngrok 例
ngrok http 8000
```

4. 画像を同時に返す場合（推奨）

`PUBLIC_BASE_URL` に公開URLを設定すると、診断結果時に
`assets/result_*.png` を自動で画像送信します。

```bash
PUBLIC_BASE_URL=https://xxxx.ngrok-free.app
```

5. 動作確認

```bash
curl https://xxxx.ngrok-free.app/health
```

`{"ok": true, ...}` が返れば稼働中です。

## リッチメニュー設定

1. `richmenu.png`（2500x1686）をこのディレクトリに配置
2. 実行権限を付与

```bash
chmod +x create_richmenu.sh
```

3. 作成スクリプト実行

```bash
source .env
./create_richmenu.sh
```

## 診断ロジックの編集ポイント

- 質問文: `app.py` の `QUESTIONS`
- 配点: 各質問の `weights`
- 体質名: `TYPE_LABELS`
- アドバイス文: `TYPE_ADVICE`

## タイプ別の結果画像を送る設定

診断結果の1位タイプに応じて、テキストの前に画像を送れます。  
`.env` に公開済み画像URL（HTTPS）を設定してください。

```bash
RESULT_IMAGE_QI_DEFICIENCY_URL=https://example.com/result_qi_deficiency.png
RESULT_IMAGE_QI_STAGNATION_URL=https://example.com/result_qi_stagnation.png
RESULT_IMAGE_BLOOD_DEFICIENCY_URL=https://example.com/result_blood_deficiency.png
RESULT_IMAGE_BLOOD_STASIS_URL=https://example.com/result_blood_stasis.png
RESULT_IMAGE_YIN_DEFICIENCY_URL=https://example.com/result_yin_deficiency.png
RESULT_IMAGE_WATER_TOXICITY_URL=https://example.com/result_water_toxicity.png
```

画像が未設定の場合は、これまで通りテキスト結果のみ送信されます。

※ `PUBLIC_BASE_URL` を設定している場合は、上記 `RESULT_IMAGE_*_URL` を
省略しても `assets` 配下の画像を自動使用します。

## 注意

- 現在のユーザー状態はメモリ保持です。再起動で消えます。
- 本番運用では Redis やDBで状態管理してください。
- この診断は医療行為ではなくセルフチェック用途です。

## 常時稼働のコツ（LINE直結）

- ngrokはテスト用途。運用は固定HTTPS URLのサーバー推奨（Render / Railway / VPSなど）
- LINE側Webhook URLは `https://<固定ドメイン>/callback` を設定
- 画像自動配信のため `PUBLIC_BASE_URL` は同じドメインに設定

## Railwayデプロイ手順

1. Railwayで `New Project` → GitHubリポジトリを選択
2. サービス設定で以下の環境変数を登録
   - `LINE_CHANNEL_ACCESS_TOKEN`
   - `LINE_CHANNEL_SECRET`
   - `PUBLIC_BASE_URL`（発行されたRailway URL）
3. デプロイ後、`https://<railway-domain>/health` で稼働確認
4. LINE DevelopersでWebhook URLを更新  
   `https://<railway-domain>/callback`
5. Webhook利用をONにし、検証が成功することを確認

このリポジトリには `railway.json`（起動コマンド/ヘルスチェック設定）が含まれているため、
そのままデプロイ可能です。
