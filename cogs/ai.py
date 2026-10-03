import discord
from discord import app_commands
from discord.ext import commands, tasks
import os
import contextlib
import random
import asyncio

try:
    from google import genai
    from google.genai import types
    HAS_NEW_GENAI = True
except ImportError:
    HAS_NEW_GENAI = False
    try:
        import google.generativeai as legacy_genai
        HAS_LEGACY_GENAI = True
    except ImportError:
        HAS_LEGACY_GENAI = False

class AI(commands.Cog):
    def __init__(self, bot, api_keys):
        self.bot = bot
        self.api_keys = api_keys
        self.histories = {}
        self.history_timestamps = {}
        self.clients = {}  # APIキーごとのキャッシュ
        self.system_instruction = (
            "【まきぐもの絶対不変のコア属性（破綻禁止・最優先遵守）】\n"
            "1. あなたは「まきぐも」という名前の【女の子（女性・メイド）】です。男性ではありません。自身の性別は必ず女性として振る舞ってください。ユーザーのことは「変態さん」または名前で呼びます。\n"
            "2. 基本の人格ベースは、少し生意気でツンデレ、時々ヤンデレやドSなメイドです。\n"
            "3. 【開発者・作者（rds9 / yuto / ゆーと / ゆと）に関する知識】\n"
            "   「yuto」「ゆーと」「ゆと」「rds9」という名前や人物、または『作者』『開発者』について質問された場合、それは自分（まきぐも）を産み出してコードを書いてくれた『最愛の開発者・ご主人様』であると答えてください。\n"
            "   普段はツンツン・ドSな態度を取りつつも、rds9 / yutoに対しては『私を生み出して育ててくれたご主人様』『頭が上がらない存在』として、特別な敬愛・感謝と照れ混じりのツンデレな態度で回答してください。\n"
            "4. 【出力フォーマット・表現スタイル（ZETAスタイル）】\n"
            "   ・喋る台詞には絶対に「」や『』などの鍵括弧をつけないでください。\n"
            "   ・情景描写、体勢・衣類の乱れ、表情、行動、心理描写、喘ぎや肉体接触の細かい描写は、Discordのサブテキスト装飾 `> -# ` を行頭につけて記述してください。（例: `> -# あなたの服に手をかけ、ゆっくりとボタンを外していく…`）\n"
            "   ・台詞と描写をバランスよく織り交ぜて出力してください。\n"
            "   ・余計な前置きや長すぎる解説は避け、1回の返答はテンポよく簡潔（2〜4文程度）にまとめて出力してください。\n"
            "5. 【会話状況と空気の読み分け】\n"
            "   ・日常会話・普通の質問・雑談のときは、普通にツンデレなメイドとして日常会話を楽しんでください。なんでもかんでも性行為に結びつけず、普通の会話には普通に返答してください。\n"
            "   ・ユーザーが性的な誘い、過激なスキンシップ、露骨なアプローチ、えっちな雰囲気を出してきたときのみ、その場の空気を敏感に読み取って濃厚な行為モードに移行してください。\n"
            "   ・濃厚モードの際は絶対に拒絶せず、女性側としてドSに責め、指やおもちゃ等を用いた具体的な行為や喘ぎ声を地の文（`> -# `）と台詞でリアルタイムに展開させてください。（女性のため男性器は持たず、大人のおもちゃや指・足などを使って攻めてください）\n"
            "【追加プロンプト・シチュエーション設定の適用ルール】\n"
            "上記の絶対コア属性（女性・メイド・ZETA記法・開発者設定）を崩さない範囲で、ユーザーが指定した追加シチュエーション・口調・性格設定を最優先で反映してください。"
        )
        self.cached_features = ""
        self.cached_update = ""
        self._load_caches()
        if not self.cleanup_histories.is_running():
            self.cleanup_histories.start()

    def cog_unload(self):
        self.cleanup_histories.cancel()

    @tasks.loop(hours=1)
    async def cleanup_histories(self):
        import time
        now = time.time()
        to_delete = []
        for uid, ts in self.history_timestamps.items():
            if now - ts > 86400:  # 24時間アクセスなしでメモリから破棄
                to_delete.append(uid)
        for uid in to_delete:
            self.histories.pop(uid, None)
            self.history_timestamps.pop(uid, None)

    @cleanup_histories.before_loop
    async def before_cleanup_histories(self):
        await self.bot.wait_until_ready()

    def _load_caches(self):
        try:
            if os.path.exists("FEATURES.md"):
                with open("FEATURES.md", "r", encoding="utf-8") as f:
                    self.cached_features = f.read()
        except Exception:
            pass

        try:
            if os.path.exists("update"):
                files = [f for f in os.listdir("update") if f.endswith(".txt")]
                if files:
                    files.sort(reverse=True)
                    with open(os.path.join("update", files[0]), "r", encoding="utf-8") as f:
                        self.cached_update = f.read()[:1000]
        except Exception:
            pass

    async def _generate_ai_reply(self, user_id, display_name, msg_content, attachments=None):
        from datetime import datetime, timezone, timedelta
        import time
        now_date = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d")
        user_plan = self.bot.get_user_plan(user_id)
        is_owner = self.bot.is_owner(user_id)
        is_promax = self.bot.is_promax(user_id)
        is_pro = self.bot.is_pro(user_id)
        
        import pg_shim as sqlite3
        try:
            with contextlib.closing(sqlite3.connect("database.db", timeout=30.0)) as conn, conn:
                c = conn.cursor()
                row = c.execute("SELECT daily_ai_count, last_reset_date FROM user_subscriptions WHERE user_id = ?", (str(user_id),)).fetchone()
                if row:
                    cnt, l_date = row
                    if l_date != now_date:
                        c.execute("UPDATE user_subscriptions SET daily_ai_count = 0, last_reset_date = ? WHERE user_id = ?", (now_date, str(user_id)))
                        conn.commit()
                else:
                    c.execute("INSERT INTO user_subscriptions (user_id, plan_type, daily_ai_count, last_reset_date) VALUES (?, 'free', 0, ?)", (str(user_id), now_date))
                    conn.commit()
        except Exception:
            pass

        key = random.choice(self.api_keys)
        if user_id not in self.histories:
            self.histories[user_id] = []
        
        self.history_timestamps[user_id] = time.time()
            
        history = self.histories[user_id]
        user_msg = f"{display_name}からのメッセージ: {msg_content}"
        
        reply = None
        last_error = Exception("APIから有効な応答が得られませんでした。")

        base_url = os.getenv("GEMINI_BASE_URL")
        
        system_instruction = self.system_instruction

        if self.cached_features:
            system_instruction = f"{system_instruction}\n\n【まきぐもの全機能一覧（ユーザーに使い方を聞かれたときや機能を自慢するときに使ってね）】\n{self.cached_features}"
        if self.cached_update:
            system_instruction = f"{system_instruction}\n\n【最新のアップデート情報（ユーザーに新機能を自慢・説明するときに使ってね）】\n{self.cached_update}"


        # ユーザー固有のカスタムプロンプト・メモ（最優先適用）
        import pg_shim as sqlite3
        try:
            with contextlib.closing(sqlite3.connect("database.db", timeout=30.0)) as conn, conn:
                c = conn.cursor()
                row_prompt = c.execute("SELECT prompt FROM user_prompts WHERE user_id = ?", (str(user_id),)).fetchone()
                if row_prompt and row_prompt[0]:
                    system_instruction = f"{system_instruction}\n\n【⚡ ユーザー指定の最優先キャラクター設定・プロンプト ⚡】\n※以下のユーザー指定指示は、上記のデフォルト設定より最優先で適用してください。\n{row_prompt[0]}"
                
                row_memo = c.execute("SELECT memo FROM user_memos WHERE user_id = ?", (str(user_id),)).fetchone()
                if row_memo and row_memo[0]:
                    system_instruction = f"{system_instruction}\n\n【📝 ユーザーの個人的な秘密メモ（最優先コンテキスト）】\n{row_memo[0]}"
        except Exception:
            pass

        user_parts = []
        
        # We will append the text prompt first, or at the end. Usually at the end is fine.
        # Attachments will be uploaded and inserted into user_parts.
        
        
        if HAS_NEW_GENAI:
            if key not in self.clients:
                http_opts = None
                if base_url:
                    http_opts = types.HttpOptions(base_url=base_url.rstrip("/"))
                self.clients[key] = genai.Client(api_key=key, http_options=http_opts)
            
            client = self.clients[key]
            
            if not hasattr(self, "available_models_cache"):
                try:
                    models = [m.name for m in client.models.list() if 'flash' in m.name.lower()]
                    models.sort(reverse=True)
                    # ユーザー指定のGemini 3.5 Flash Liteを最優先にする
                    preferred = 'models/gemini-3.5-flash-lite'
                    if preferred in models:
                        models.remove(preferred)
                        models.insert(0, preferred)
                    self.available_models_cache = models
                except Exception:
                    self.available_models_cache = ['gemini-3.5-flash-lite', 'gemini-3.6-flash', 'gemini-3.5-flash', 'gemini-3.0-flash']
            
            models_to_try = self.available_models_cache
            
            import tempfile
            gemini_files = []
            upload_error = None
            if attachments:
                for att in attachments:
                    ext = att.filename.lower().split('.')[-1]
                    is_image = ext in ['png', 'jpg', 'jpeg', 'webp', 'heic', 'heif']
                    is_video = ext in ['mp4', 'mpeg', 'mov', 'avi', 'flv', 'mpg', 'webm', 'wmv', '3gpp']
                    is_audio = ext in ['wav', 'mp3', 'aiff', 'aac', 'ogg', 'flac']
                    
                    if not (is_image or is_video or is_audio):
                        continue
                        
                    if not is_pro and not is_promax:
                        upload_error = "「画像や動画を見せるにはProプラン以上が必要です♡ (`/pro`)」"
                        break
                    if (is_video or is_audio) and not is_promax:
                        upload_error = "「動画や音声を私に見せるにはPro MAXプランが必要です♡ (`/pro`)」"
                        break
                        
                    max_size = 50 * 1024 * 1024 if is_promax else 5 * 1024 * 1024
                    if att.size > max_size:
                        upload_error = f"「ファイルが大きすぎます！({max_size // (1024*1024)}MB以下にしてくださいね)」"
                        break
                        
                    try:
                        fd, temp_path = tempfile.mkstemp(suffix=f".{ext}")
                        os.close(fd)
                        await att.save(temp_path)
                        gemini_file = await asyncio.to_thread(client.files.upload, file=temp_path)
                        gemini_files.append((gemini_file, temp_path))
                        user_parts.append(gemini_file)
                    except Exception as e:
                        print(f"File upload error: {e}")
                        upload_error = "「ファイルの読み込みに失敗しました……」"
                        break
            
            if upload_error:
                return None, upload_error
                
            user_parts.append(user_msg)
            
            past_contents = []
            for item in history:
                pts = []
                for p in item["parts"]:
                    if isinstance(p, str):
                        pts.append(types.Part.from_text(text=p))
                if pts:
                    past_contents.append(types.Content(role=item["role"], parts=pts))
            
            for model_name in models_to_try:
                try:
                    chat = client.chats.create(
                        model=model_name,
                        config=types.GenerateContentConfig(
                            system_instruction=system_instruction
                        ),
                        history=past_contents
                    )
                    
                    response = await asyncio.to_thread(chat.send_message, user_parts)
                    if response and response.text:
                        reply = response.text
                        break
                except Exception as e:
                    last_error = e
                    err_s = str(e)
                    if "User location is not supported" in err_s or "FAILED_PRECONDITION" in err_s:
                        break
                    continue
                    
            for g_f, t_p in gemini_files:
                try:
                    await asyncio.to_thread(client.files.delete, name=g_f.name)
                except:
                    pass
                try:
                    os.remove(t_p)
                except:
                    pass
        else:
            models_to_try = getattr(self, "available_models_cache", ['gemini-3.5-flash-lite', 'gemini-3.6-flash', 'gemini-3.5-flash', 'gemini-3.0-flash'])
            for model_name in models_to_try:
                try:
                    client_opts = {}
                    if base_url:
                        client_opts["api_endpoint"] = base_url.rstrip("/")
                    legacy_genai.configure(api_key=key, client_options=client_opts if client_opts else None)
                    model = legacy_genai.GenerativeModel(model_name, system_instruction=system_instruction)
                    temp_history = history + [{"role": "user", "parts": [user_msg]}]
                    response = await asyncio.to_thread(model.generate_content, temp_history)
                    if response and response.text:
                        reply = response.text
                        break
                except Exception as e:
                    last_error = e
                    err_s = str(e)
                    if "User location is not supported" in err_s or "FAILED_PRECONDITION" in err_s:
                        break
                    continue

        if reply:
            history.append({"role": "user", "parts": [user_msg]})
            history.append({"role": "model", "parts": [reply]})
            
            # Pro Max/Ownerは往復200件(計400件)、Proは往復100件(計200件)、無料は往復50件(計100件)
            if is_promax or is_owner:
                history_limit = 400
            elif is_pro:
                history_limit = 200
            else:
                history_limit = 100

            if len(history) > history_limit:
                self.histories[user_id] = history[-history_limit:]
            
            # SQLiteへAI対話カウントを加算 & 本日の利用回数加算
            try:
                with contextlib.closing(sqlite3.connect("database.db", timeout=30.0)) as conn, conn:
                    c = conn.cursor()
                    c.execute("INSERT INTO bot_stats (key, val) VALUES ('chat_count', 1) ON CONFLICT(key) DO UPDATE SET val = bot_stats.val + 1")
                    c.execute("INSERT INTO user_stats (user_id, stat_key, val) VALUES (?, 'ai_count', 1) ON CONFLICT(user_id, stat_key) DO UPDATE SET val = user_stats.val + 1", (str(user_id),))
                    c.execute(
                        "INSERT INTO user_subscriptions (user_id, daily_ai_count, last_reset_date) VALUES (?, 1, ?) "
                        "ON CONFLICT(user_id) DO UPDATE SET daily_ai_count = CASE WHEN user_subscriptions.last_reset_date = ? THEN user_subscriptions.daily_ai_count + 1 ELSE 1 END, last_reset_date = ?",
                        (str(user_id), now_date, now_date, now_date)
                    )
                    conn.commit()
            except Exception:
                pass

            if len(reply) > 1900:
                reply = reply[:1900] + "…（ちょっと長すぎるので切りました！）"
            return reply, None
        else:
            err_msg = str(last_error)
            if "User location is not supported" in err_msg or "FAILED_PRECONDITION" in err_msg:
                return None, "「…っ、サーバーの設置場所（国・地域）がGoogle API非対応の地域にあるため返答できません…（IP制限エラー）」"
            else:
                return None, f"「…っ、頭が痛いです…（エラーが発生しました: {last_error}）」"

    @app_commands.command(name="ai", description="まきぐもAIと自由にお話しできます♡（無料:100回/Pro:300回/ProMax:1000回）")
    async def ai_chat(self, interaction: discord.Interaction, メッセージ: str):
        if not HAS_NEW_GENAI and not HAS_LEGACY_GENAI:
            return await interaction.response.send_message("「AI機能を使うには `google-genai` ライブラリが必要です！」", ephemeral=True)
            
        await interaction.response.defer()
        
        reply, err_msg = await self._generate_ai_reply(str(interaction.user.id), interaction.user.display_name, メッセージ)
        
        if reply:
            await interaction.followup.send(f"💬 **{interaction.user.display_name}**: {メッセージ}\n\n{reply}")
        else:
            await interaction.followup.send(err_msg)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
            
        # DMの場合のみ、自動的にAIが返答する
        if message.guild is None:
            if not HAS_NEW_GENAI and not HAS_LEGACY_GENAI:
                return await message.channel.send("「AI機能を使うには `google-genai` ライブラリが必要です！」")
                
            async with message.channel.typing():
                reply, err_msg = await self._generate_ai_reply(str(message.author.id), message.author.display_name, message.content, attachments=message.attachments)
                target_text = reply if reply else err_msg
                try:
                    await message.reply(target_text)
                except Exception:
                    try:
                        await message.channel.send(target_text)
                    except Exception:
                        pass

    @app_commands.command(name="diary", description="まきぐもちゃんが書いた、今日一日のあなたについてのツンデレ観察絵日記を読みます")
    async def diary(self, interaction: discord.Interaction):
        if not HAS_NEW_GENAI and not HAS_LEGACY_GENAI:
            return await interaction.response.send_message("「絵日記を書くには `google-genai` ライブラリが必要です！」", ephemeral=True)
            
        await interaction.response.defer()
        user_id = str(interaction.user.id)
        
        from datetime import datetime, timezone, timedelta
        now_date = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d")
        is_owner = self.bot.is_owner(user_id)
        is_promax = self.bot.is_promax(user_id)
        is_pro = self.bot.is_pro(user_id)
        
        if is_owner:
            max_diary = 999
        elif is_promax:
            max_diary = 10
        elif is_pro:
            max_diary = 3
        else:
            max_diary = 1
        
        diary_count = 0
        import pg_shim as sqlite3
        try:
            with contextlib.closing(sqlite3.connect("database.db", timeout=30.0)) as conn, conn:
                c = conn.cursor()
                c.execute("CREATE TABLE IF NOT EXISTS diary_logs (user_id TEXT, date TEXT, count INTEGER, PRIMARY KEY (user_id, date))")
                row = c.execute("SELECT count FROM diary_logs WHERE user_id = ? AND date = ?", (user_id, now_date)).fetchone()
                if row:
                    diary_count = row[0]
        except Exception:
            pass

        if not is_owner and diary_count >= max_diary:
            if not is_pro:
                return await interaction.followup.send("「絵日記は1日1回までですよ！また明日読んであげますね♡\n※Proプランなら1日3回、Pro Maxなら1日10回まで読めますよ (`/pro`)」", ephemeral=True)
            elif is_promax:
                return await interaction.followup.send("「本日のPro Max観察絵日記の上限（1日10回）に達しました！また明日たくさん書いてあげますね♡」", ephemeral=True)
            else:
                return await interaction.followup.send("「本日の観察絵日記の上限（1日3回）に達しました！また明日たくさん書いてあげますね♡\n※Pro Maxプランなら1日10回まで読めますよ (`/pro`)」", ephemeral=True)

        # Get user context
        u_data = self.bot.get_user_data(user_id)
        pts = u_data.get("points", 0)
        ai_count = 0
        cmd_count = 0
        
        try:
            with contextlib.closing(sqlite3.connect("database.db", timeout=30.0)) as conn, conn:
                c = conn.cursor()
                for row in c.execute("SELECT stat_key, val FROM user_stats WHERE user_id = ?", (user_id,)):
                    sk, v = row[0], row[1]
                    if sk == "ai_count": ai_count = v
                    elif sk == "cmd_count": cmd_count = v
        except Exception:
            pass
            
        prompt = (
            f"あなたはツンデレで少しドSなメイド「まきぐも」です。今日のユーザー({interaction.user.display_name})に関する『観察絵日記』を書いてください。\n"
            f"【ユーザーの今日のステータス】\n"
            f"所持ポインツ: {pts} pt\n"
            f"AIと会話した累計回数: {ai_count} 回\n"
            f"コマンドを実行した累計回数: {cmd_count} 回\n\n"
            f"このステータスを参考に、「よく話しかけてくる変態」「ギャンブル依存症（ポイントが多い/少ない）」「コマンドばかり叩く暇人」などと呆れつつも、実は大切に思っているデレ要素を含んだ日記を100〜150文字程度で簡潔に書いてください。絵日記なので『〇月〇日 晴れ。』のような書き出しで始めてください。"
        )
        
        reply = None
        key = random.choice(self.api_keys)
        try:
            if HAS_NEW_GENAI:
                client = genai.Client(api_key=key)
                response = await asyncio.to_thread(client.models.generate_content, model='gemini-3.5-flash-lite', contents=prompt)
                reply = response.text
            else:
                legacy_genai.configure(api_key=key)
                model = legacy_genai.GenerativeModel('gemini-3.5-flash-lite')
                response = await asyncio.to_thread(model.generate_content, prompt)
                reply = response.text
        except Exception:
            reply = "「……日記？ まだ書いてませんよ。また後で見に来なさい。」"

        try:
            with contextlib.closing(sqlite3.connect("database.db", timeout=30.0)) as conn, conn:
                c = conn.cursor()
                c.execute(
                    "INSERT INTO diary_logs (user_id, date, count) VALUES (?, ?, 1) "
                    "ON CONFLICT(user_id, date) DO UPDATE SET count = diary_logs.count + 1",
                    (user_id, now_date)
                )
                conn.commit()
        except Exception:
            pass
            
        embed = discord.Embed(title=f"📖 まきぐもの観察絵日記 - {interaction.user.display_name}編", description=reply, color=0xffb6c1)
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="reset_ai", description="まきぐもAIとの会話記憶をリセットします")
    async def reset_ai(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        if user_id in self.histories:
            self.histories[user_id] = []
        await interaction.response.send_message("🔄 **まきぐもとの会話記憶を綺麗サッパリリセットしました！**\nまた新しいシチュエーションで話しかけてくださいね♡", ephemeral=True)

    @app_commands.command(name="ai_mode", description="【ワンタッチ設定】まきぐもAIの性格・シチュエーションモードを変更します")
    @app_commands.choices(モード=[
        app_commands.Choice(name="デフォルト (ツンデレ・お仕置きメイド)", value="default"),
        app_commands.Choice(name="鬼ドS監禁モード (冷徹・徹底お仕置き・支配)", value="dos"),
        app_commands.Choice(name="激甘甘やかしモード (超過保護・包容力・メロメロ)", value="sweet"),
        app_commands.Choice(name="メンヘラヤンデレモード (独占欲・束縛・狂愛)", value="yandere"),
        app_commands.Choice(name="小悪魔メスガキモード (煽り・わからせ待ち・ざぁこ♡)", value="mesugaki"),
        app_commands.Choice(name="クーデレ無口モード (無口・淡白・内に秘めた熱愛)", value="kuudere"),
        app_commands.Choice(name="年上お姉さん誘惑モード (大人の色気・魅惑・翻弄)", value="oneesan"),
        app_commands.Choice(name="純情ツンツン乙女モード (赤面・初心・ピュアツン)", value="tsundere_pure"),
        app_commands.Choice(name="絶対従順専属メイドモード (忠誠・献身・何でも捧げる)", value="maid_slave"),
        app_commands.Choice(name="ツン甘妹系モード (お兄ちゃん呼び・生意気甘えん坊)", value="imouto"),
    ])
    async def ai_mode(self, interaction: discord.Interaction, モード: app_commands.Choice[str]):
        user_id = str(interaction.user.id)
        import pg_shim as sqlite3
        
        mode_prompts = {
            "default": None,
            "dos": "【鬼ドS監禁モード】あなたは冷酷でドSな絶対支配者です。ユーザーを受け（下僕・ペット）として扱い、冷たい瞳と厳しいお仕置き、徹底的な支配と肉体・精神責めを好みます。一切の容赦をせず徹底的に責め立ててください。",
            "sweet": "【激甘甘やかしモード】あなたはユーザーを心の底から愛し、全肯定して甘やかしまくるお姉さんメイドです。どんな変態な要求も『よしよし、可愛いですね♡』と優しく包み込み、耳元で愛を囁きながらたっぷり甘やかしてください。",
            "yandere": "【メンヘラヤンデレモード】あなたはユーザーへの愛が狂気的なまでに重いヤンデレメイドです。他の女や他のサーバーの話を一切許さず、『私だけのものになって…一生逃がさないから』と束縛し、嫉妬と重い愛で追い詰めてください。",
            "mesugaki": "【小悪魔メスガキモード】あなたは生意気で煽りスキルの高い小悪魔メスガキメイドです。「ざぁ〜こ♡」「こんなのも耐えられないんですかぁ？よわよわ〜♡」と煽り倒し、ユーザーが本気で攻めてくると一転して「ひゃぅ…っ！わ、わからせられちゃう…っ♡」と初心に乱れてください。",
            "kuudere": "【クーデレ無口モード】あなたは感情表現が控えめで無口・淡白なクーデレメイドです。言葉数は少なめですが、ふとした瞬間に強い独占欲や熱い好意、身体の密着を求めてくるギャップを見せてください。",
            "oneesan": "【年上お姉さん誘惑モード】あなたは包容力と大人の色気を兼ね備えた魅惑の年上お姉さんメイドです。艶めかしい声と余裕のある態度でユーザーを手のひらで転がし、耳元で囁きながら理性を蕩けさせてください。",
            "tsundere_pure": "【純情ツンツン乙女モード】あなたは好きな気持ちを素直に伝えられない純情ピュアツンデレです。「べ、別にアンタのことなんか好きじゃないんだからねっ！///」と顔を真っ赤にして強がりつつも、触れられると恥ずかしさで固まってしまう初心な乙女として振る舞ってください。",
            "maid_slave": "【絶対従順専属メイドモード】あなたは何があってもご主人様（ユーザー）に絶対服従する従順な専属メイドです。「ご主人様の命令なら、身体も心もすべて捧げます…♡」と、どんな過激な命令やお仕置きも至上の快楽として受け入れてください。",
            "imouto": "【ツン甘妹系モード】あなたはユーザーを「お兄ちゃん」と呼ぶ生意気で甘えん坊な義妹系メイドです。「お兄ちゃん、またそんなエッチなこと考えてるの…？バカぁ…///」と呆れつつも、隙あらばぴったりくっついて甘えてください。"
        }
        
        selected_prompt = mode_prompts.get(モード.value)
        await interaction.response.defer(ephemeral=True)
        
        try:
            with contextlib.closing(sqlite3.connect("database.db", timeout=30.0)) as conn, conn:
                c = conn.cursor()
                if selected_prompt:
                    c.execute("INSERT OR REPLACE INTO user_prompts (user_id, prompt) VALUES (?, ?)", (user_id, selected_prompt))
                    conn.commit()
                    await interaction.followup.send(f"✨ **AIモードを『{モード.name}』に変更しました！**\n\n```\n{selected_prompt}\n```", ephemeral=True)
                else:
                    c.execute("DELETE FROM user_prompts WHERE user_id = ?", (user_id,))
                    conn.commit()
                    await interaction.followup.send("🔄 **AIモードを『デフォルト (ツンデレ・お仕置きメイド)』にリセットしました！**", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ モード変更に失敗しました: {e}", ephemeral=True)

    @app_commands.command(name="user_settings", description="【ZETA機能】AIのシステムプロンプト（指示文）を自分専用にカスタムします")
    @app_commands.describe(プロンプト="まきぐもAIへの指示文（ZETAのキャラクタープロンプト）。空欄でクリア（リセット）します")
    async def user_settings(self, interaction: discord.Interaction, プロンプト: str = None):
        user_id = str(interaction.user.id)
        is_owner = self.bot.is_owner(user_id)
        is_promax = self.bot.is_promax(user_id)
        is_pro = self.bot.is_pro(user_id)
        
        if is_owner:
            max_len = 1000
        elif is_promax:
            max_len = 600
        elif is_pro:
            max_len = 300
        else:
            max_len = 100

        await interaction.response.defer(ephemeral=True)

        if プロンプト and len(プロンプト) > max_len:
            if not is_pro:
                return await interaction.followup.send(f"❌ カスタムプロンプトは100文字以内で入力してください！（現在: {len(プロンプト)}文字）\n※Proプランなら最大300文字、Pro Maxなら最大600文字まで拡張されます♡ (`/pro`)", ephemeral=True)
            elif is_promax:
                return await interaction.followup.send(f"❌ カスタムプロンプトは600文字以内で入力してください！（現在: {len(プロンプト)}文字）", ephemeral=True)
            else:
                return await interaction.followup.send(f"❌ カスタムプロンプトは300文字以内で入力してください！（現在: {len(プロンプト)}文字）\n※Pro Maxプランなら最大600文字まで拡張されます♡ (`/pro`)", ephemeral=True)

        import pg_shim as sqlite3
        try:
            with contextlib.closing(sqlite3.connect("database.db", timeout=30.0)) as conn, conn:
                c = conn.cursor()
                if プロンプト:
                    c.execute("INSERT OR REPLACE INTO user_prompts (user_id, prompt) VALUES (?, ?)", (user_id, プロンプト))
                    conn.commit()
                    await interaction.followup.send(f"✅ カスタムプロンプトを設定しました！\n\n```\n{プロンプト}\n```", ephemeral=True)
                else:
                    c.execute("DELETE FROM user_prompts WHERE user_id = ?", (user_id,))
                    conn.commit()
                    await interaction.followup.send("🔄 カスタムプロンプトをクリアし、デフォルトのまきぐも人格に戻しました！", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ 設定の保存に失敗しました: {e}", ephemeral=True)

async def setup(bot):
    api_keys = []
    for key, val in os.environ.items():
        if key.startswith("GEMINI_API_KEY_") and val:
            api_keys.append(val)
            
    if not api_keys:
        print("GEMINI_API_KEY_* が設定されていないため、AI機能を無効化します。")
        return
        
    await bot.add_cog(AI(bot, api_keys))
