# まきぐも Bot 内部 Web API 仕様書

まきぐも Bot（`main.py`）が提供する HTTP API エンドポイントの仕様です。
Webサイト（`rds9.net/makigumo`）のステータス表示やお試しチャットなどで利用されています。

---

## 1. 基本仕様

- **ベースポート**: `8080`（環境変数 `PORT` で変更可能）
- **バインド**: `0.0.0.0:8080`
- **CORS**: 全エンドポイントで `Access-Control-Allow-Origin: *` 対応
- **文字コード**: UTF-8
- **プロセス管理**: PM2 (`makigumo`)

---

## 2. エンドポイント一覧

| メソッド | パス | 説明 |
|---|---|---|
| `GET` | `/` | 稼働確認（プレーンテキスト） |
| `GET` | `/api/stats` | リアルタイム稼働統計情報（サーバー数・ユーザー数・対話数等） |
| `GET` | `/server_count.json` | `/api/stats` と同等の統計データ |
| `GET` | `/api/health` | ヘルスチェック用軽量データ |
| `GET` | `/health` | `/api/health` のエイリアス |
| `POST` | `/api/trial` | まきぐも AI お試しチャット（セッション・記憶保持対応） |
| `OPTIONS` | `/api/trial` | CORS プリフライト用 |

---

## 3. 各エンドポイント詳細

### 3.1. `GET /`
Botの稼働確認用ルートエンドポイント。

- **Response Header**: `Content-Type: text/plain`
- **Response Body**:
  ```text
  Makigumo Bot v4.1 is alive and watching you♡
  ```

---

### 3.2. `GET /api/stats`
Botの稼働状況や各種メトリクスを返却します。Webサイトの監視中カウンター等で使用されます。

- **Response Header**: `Content-Type: application/json`
- **Response Body**:
  ```json
  {
    "status": "online",
    "version": "v4.1",
    "guilds": 46,
    "users": 1374,
    "ping": 125.4,
    "chat_count": 8520,
    "cmd_count": 1420,
    "uptime_seconds": 1542,
    "campaign_active": true,
    "bot_name": "まきぐも",
    "bot_id": "1513527535168651314"
  }
  ```

#### フィールド定義
| フィールド | 型 | 説明 |
|---|---|---|
| `status` | string | Botの稼働ステータス (`online`) |
| `version` | string | Botバージョン |
| `guilds` | integer | 参加サーバー数 |
| `users` | integer | 参加サーバーの合計ユーザー数 |
| `ping` | float | Discord Gateway とのレイテンシ (ms) |
| `chat_count` | integer | 累計 AI チャット対話回数（SQLite `bot_stats`） |
| `cmd_count` | integer | 累計スラッシュコマンド実行回数（SQLite `bot_stats`） |
| `uptime_seconds` | integer | プロセス起動時からの稼働秒数 |
| `campaign_active` | boolean | 全有料機能無料開放キャンペーン中かどうか |
| `bot_name` | string | Discord上のBot表示名 |
| `bot_id` | string | Discord Application / Client ID |

---

### 3.3. `GET /api/health`
死活監視・ロードバランサー・モニタリング用の軽量エンドポイント。

- **Response Header**: `Content-Type: application/json`
- **Response Body**:
  ```json
  {
    "status": "ok",
    "latency_ms": 125.4,
    "guilds": 46,
    "users": 1374,
    "uptime_seconds": 1542,
    "campaign_active": true
  }
  ```

---

### 3.4. `POST /api/trial`
Discord Bot の AI 人格（`cogs/ai.py`）を直接呼び出すお試しチャットエンドポイント。
セッションIDごとの会話履歴保持（文脈記憶）およびリセットに対応しています。

- **Request Header**: `Content-Type: application/json`

#### ① 通常チャット送信
- **Request Body**:
  ```json
  {
    "action": "chat",
    "message": "こんにちは！私の名前はテストくんだよ",
    "session_id": "web_user123",
    "user_name": "テストくん"
  }
  ```

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|---|---|---|---|---|
| `action` | string | 任意 | `"chat"` | `"chat"` または `"reset"` |
| `message` | string | 必須 | - | ユーザーの発言（最大300文字） |
| `session_id` | string | 任意 | 自動生成 | セッション識別子（同一IDで文脈を保持） |
| `user_name` | string | 任意 | `"変態さん"` | まきぐもが呼ぶユーザー名（最大20文字） |

- **Response Body (成功時)**:
  ```json
  {
    "status": "ok",
    "reply": "> -# あなたの顔をじっと見つめ、呆れたようにため息をつく…\nふん、テストくんですか。変態さん、私に何の用ですか？",
    "session_id": "web_user123",
    "turn_count": 1
  }
  ```

#### ② 会話記憶リセット
- **Request Body**:
  ```json
  {
    "action": "reset",
    "session_id": "web_user123"
  }
  ```

- **Response Body**:
  ```json
  {
    "status": "ok",
    "action": "reset",
    "reply": "記憶をリセットしました……。ふん、また最初からやり直すつもりですか？",
    "session_id": "web_user123",
    "turn_count": 0
  }
  ```

---

## 4. ZETA記法レスポンスの仕様

`reply` フィールドは Discord Bot と同一の **ZETA記法** で返却されます。

1. **台詞**: 鉤括弧（「」）は付きません。地の文と混在して出力されます。
2. **ト書き（情景・行動・表情・心理描写）**: 行頭に `> -# ` が付与されます。
   - Discord 上では引用＋薄文字（サブテキスト）としてレンダリングされます。
   - Web 上では引用バー＋斜体・薄文字としてレンダリングすることを推奨します。

### Web フロントエンド向け正規表現
```javascript
// 行頭の > -# を抽出
if (/^>\s*-#\s*/.test(line)) {
  const text = line.replace(/^>\s*-#\s*/, '');
  // ト書き用スタイル（斜体・薄文字・引用バー）で描画
}
```

---

## 5. 接続テスト例 (curl)

```bash
# ヘルスチェック
curl -s http://127.0.0.1:8080/api/health

# 統計情報
curl -s http://127.0.0.1:8080/api/stats

# お試しチャット送信
curl -s -X POST http://127.0.0.1:8080/api/trial \
  -H "Content-Type: application/json" \
  -d '{"message": "おはよ！", "session_id": "web_test", "user_name": "ご主人様"}'

# 会話記憶リセット
curl -s -X POST http://127.0.0.1:8080/api/trial \
  -H "Content-Type: application/json" \
  -d '{"action": "reset", "session_id": "web_test"}'
```
