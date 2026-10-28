# まきぐも (Makigumo Bot) v4.2

Google Gemini API を利用した Discord Bot。

## 主な機能

- **Gemini AIチャット**: `/ai` コマンドおよびDMでの会話に対応（会話記憶機能あり）。画像・動画・音声のマルチモーダル入力に対応。
- **専用AIスレッド (`/ai_thread`)**: コマンドやメンション不要で会話できる専用スレッドや常駐チャンネルを作成可能。
- **プリセット共有 (`/preset`)**: キャラクタープロンプトの適用およびユーザー間での共有。
- **お部屋・着せ替え・ペット (`/room`)**: 衣装変更、ペットや家具の配置機能。
- **対戦・ミニゲーム (`/blackjack`, `/duel`, `/slot`)**: ブラックジャック、じゃんけん、チキンレース、スロット等。
- **レベル・経験値システム (`/stats`)**: メッセージ送信に応じた経験値と称号の獲得。
- **全コマンド仕様**: 実装されている全コマンドの解説・引数一覧は [FEATURES.md](FEATURES.md) を参照してください。

## 必要な環境

- Python 3.9 以上
- 依存ライブラリ: `discord.py`, `python-dotenv`, `google-genai` (または `google-generativeai`)

## セットアップ手順

1. リポジトリをクローンまたはダウンロードします。
2. 必要なパッケージをインストールします。
   ```bash
   pip install -r requirements.txt
   ```
3. `.env.example` をコピーして `.env` ファイルを作成し、各種環境変数を設定します。
   ```bash
   cp .env.example .env
   ```
   - `DISCORD_TOKEN`: DiscordのBotトークン
   - `GEMINI_API_KEY_1`〜`10`: Google Gemini APIキー（キーローテーション対応）
   - `ADMIN_USER_ID`: Bot管理者のDiscordユーザーID
   - `GEMINI_BASE_URL`: (任意) プロキシURL

## 起動方法

```bash
# シェルスクリプトで起動
bash start.sh

# 直接起動
python main.py

# Docker Compose で起動
docker-compose up -d --build
```

## 構成

- `main.py`: メインプロセスおよびSQLite3連携
- `cogs/`:
  - `cogs.events`: イベント監視、ステータスローテーション
  - `cogs.ai`: Gemini AIチャットエンジン
  - `cogs.leveling`: レベル・XPシステム
  - `cogs.economy`: ポインツ・経済システム
  - `cogs.billing`: 支援・寄付管理
