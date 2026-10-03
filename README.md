# ☁️ まきぐも (Makigumo Bot) v3.6

サーバー＆DMに常駐してユーザーを監視・お世話・癒やし・お仕置きする、Google Gemini AI搭載の多機能Discord Botです。

## 🌟 v3.6 の主な特徴・機能
- 🤖 **ZETAスタイル Gemini AIチャット**: `/ai` コマンドおよび **DM直接送信** でAIと濃厚な会話が楽しめます（会話記憶30件）。台詞からの鍵括弧（「」）を撤廃し、Discordの薄文字装飾（`> -# `）を用いた臨場感あふれる情景描写・R-18ロールプレイを完全再現。
- 🧠 **自己認識・自己学習AI**: Bot自身の機能一覧(`FEATURES.md`)や最新アップデート情報(`update/`)をAIが常に読み込んでいるため、ユーザーからの「どんな機能がある？」「最近何が変わった？」等の質問にスマートに回答します。
- ⚙️ **カスタムプロンプト (`/user_settings`)**: ユーザーごとに自分専用のZETAキャラクタープロンプトをSQLiteデータベースへ自由・無制限に保存可能。
- 🌐 **Cloudflare Workers プロキシ対応**: `.env` に `GEMINI_BASE_URL` を設定することで、ホスティング環境（MrtCloud等）のIP地域制限を100%回避してGoogle Gemini APIを利用可能。
- 📈 **レベル・経験値システム (`/level`)**: メッセージ送信でレベルアップ＆ポインツボーナス獲得。
- 🎰 **カジノ・経済・ショップシステム**: 変態ポインツを使った `/gamble`、`/slot`、`/shop` などのゲーム機能。
- 💾 **SQLite3 データベース完全移行**: 設定やポインツ・レベルデータはすべて `database.db` に安全かつ高速に自動保存。
- 🔗 **公式サーバー＆寄付機能 (`/server`, `/donate`)**: 公式Discordサーバーリンクや開発者（rds9）への支援窓口を完備。
- 🟣 **常時「配信中（Streaming）」＆3秒爆速ステータスローテーション**: 5秒以下の高速で監視メンバー数、監視サーバー数、ping、Powered by rds9team をローテーション表示（`https://rds9.net` リンク付き）。
- 📖 **全コマンド仕様書**: 実装されている全コマンドの解説・引数一覧は [FEATURES.md](FEATURES.md) を参照してください。
## 必要な環境
- Python 3.9 以上推奨
- 依存ライブラリ: `discord.py`, `python-dotenv`, `google-genai` (または `google-generativeai`)

## セットアップ方法
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
   - `GEMINI_BASE_URL`: (任意) Cloudflare Workers等のプロキシURL

## 起動方法
```bash
# シェルスクリプトで起動
bash start.sh

# 直接起動
python main.py

# Docker / Docker Compose で起動
docker-compose up -d --build
```

## 構成と設定
- `main.py`: BotのメインプロセスおよびSQLite3連携
- `cogs/`:
  - `cogs.events`: イベント監視、常時配信ステータスローテーション
  - `cogs.ai`: Gemini AIエンジン（ZETAスタイル、DMチャット、`/user_settings`）
  - `cogs.leveling`: レベル・XPシステム
  - `cogs.economy`: ポインツ・カジノ・ショップ
  - `cogs.roleplay`: `/help`、`/server`、`/donate`、シチュエーションコマンド
- `update/`: アップデートログ履歴（`v3.6.txt` 等）
- `database.db`: 自動生成されるSQLite3データベース

## ライセンスと利用に関するお願い
このプロジェクトは **[GNU Affero General Public License v3.0 (AGPL-3.0)](LICENSE)** の下で公開されています。
**⚠️ MITライセンスではありません。** コードの改変や、このBotをネットワーク越しでサービスとして提供（自分のサーバーで動かして他の人に使わせる等）する場合、改変したソースコードの公開義務が発生するなど、厳格な条件がありますのでご注意ください。

また、このBotを導入・利用される際や、ご自身で派生Botを作成される際は、Discordで **`rds9`** （メール: [rds9discord@outlook.jp](mailto:rds9discord@outlook.jp)）まで一言ご連絡いただけると嬉しいです！
