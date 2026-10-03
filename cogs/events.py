import discord
from discord.ext import commands, tasks
import json
import os
import contextlib
import shutil
import glob
import sys
import asyncio
from datetime import datetime, time, timezone, timedelta

class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.status_index = 0
        if not self.update_status_loop.is_running():
            self.update_status_loop.start()
        if not self.daily_restart.is_running():
            self.daily_restart.start()
        if not self.background_economy_saver.is_running():
            self.background_economy_saver.start()
        if not self.check_birthdays.is_running():
            self.check_birthdays.start()
        if not self.periodic_server_count_saver.is_running():
            self.periodic_server_count_saver.start()
        if not self.db_backup_task.is_running():
            self.db_backup_task.start()

    def cog_unload(self):
        self.update_status_loop.cancel()
        self.daily_restart.cancel()
        self.background_economy_saver.cancel()
        self.check_birthdays.cancel()
        self.periodic_server_count_saver.cancel()
        self.db_backup_task.cancel()

    def _is_ws_available(self) -> bool:
        try:
            if not self.bot.is_ready() or self.bot.is_closed():
                return False
            if hasattr(self.bot, 'shards') and self.bot.shards:
                for shard in self.bot.shards.values():
                    if hasattr(shard, 'is_closed') and shard.is_closed():
                        return False
                    if hasattr(shard, 'is_connected') and not shard.is_connected():
                        return False
                    if hasattr(shard, 'is_ws_ratelimited') and shard.is_ws_ratelimited():
                        return False
            else:
                if hasattr(self.bot, 'ws') and self.bot.ws is not None:
                    if getattr(self.bot.ws, 'closed', False):
                        return False
                if getattr(self.bot, 'is_ws_ratelimited', None) and self.bot.is_ws_ratelimited():
                    return False
            return True
        except Exception:
            return False

    @commands.Cog.listener()
    async def on_ready(self):
        version = "V14"
        update_dir = "update"
        if os.path.exists(update_dir):
            files = [f for f in os.listdir(update_dir) if f.endswith(".txt")]
            if files:
                files.sort(reverse=True)
                version = files[0].replace('.txt', '')
        print(f'ログイン成功: {self.bot.user.name} {version} (Gamble Ready)')
        await self.update_bot_status()
        await self.save_server_count()

    @commands.Cog.listener()
    async def on_resumed(self):
        await self.update_bot_status()

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        await self.save_server_count()

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        await self.save_server_count()

    async def save_server_count(self):
        if not self.bot.is_ready() or self.bot.is_closed():
            return
        try:
            total_members = sum(guild.member_count for guild in self.bot.guilds if guild.member_count)
            guild_count = len(self.bot.guilds)
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            count_data = {"guilds": guild_count, "users": total_members}
            with open("server_count.json", "w", encoding="utf-8") as f:
                json.dump(count_data, f, ensure_ascii=False, indent=4)

            log_lines = [
                f"=== まきぐも 稼働状況ログ ({now_str}) ===\n",
                f"導入サーバー数: {guild_count}\n",
                f"総監視ユーザー数: {total_members}\n",
                "----------------------------------------\n"
            ]
            for guild in self.bot.guilds:
                owner_name = guild.owner.display_name if guild.owner else f"ID:{guild.owner_id}"
                log_lines.append(f"- {guild.name} (ID: {guild.id}) | 鯖主: {owner_name} | {guild.member_count}人\n")
            with open("log.txt", "w", encoding="utf-8") as f:
                f.writelines(log_lines)
        except Exception as e:
            print(f"⚠️ サーバー数保存エラー: {e}")

    async def update_bot_status(self):
        if not self._is_ws_available():
            return

        try:
            total_members = sum(guild.member_count for guild in self.bot.guilds if guild.member_count)
            guild_count = len(self.bot.guilds)
            
            try:
                latency_ms = round(self.bot.latency * 1000)
            except (OverflowError, ValueError):
                latency_ms = 0
                
            stream_url = "https://rds9.net"

            chat_count, cmd_count = 0, 0
            import pg_shim as sqlite3
            try:
                with contextlib.closing(sqlite3.connect("database.db", timeout=30.0)) as conn, conn:
                    c = conn.cursor()
                    r1 = c.execute("SELECT val FROM bot_stats WHERE key = 'chat_count'").fetchone()
                    if r1: chat_count = r1[0]
                    r2 = c.execute("SELECT val FROM bot_stats WHERE key = 'cmd_count'").fetchone()
                    if r2: cmd_count = r2[0]
            except Exception:
                pass

            if self.status_index == 0:
                status_text = f"{total_members}人の変態を監視中♡ | /help"
            elif self.status_index == 1:
                status_text = f"{guild_count}サーバーで監視中♡"
            elif self.status_index == 2:
                status_text = f"💬 {chat_count}回の会話 | ⚡ {cmd_count}回のコマンド"
            elif self.status_index == 3:
                status_text = f"ping: {latency_ms}ms"
            else:
                status_text = "Powered by rds9team"

            activity = discord.Streaming(name=status_text, url=stream_url)
            self.status_index = (self.status_index + 1) % 5

            await self.bot.change_presence(status=discord.Status.online, activity=activity)
        except (discord.errors.ConnectionClosed, discord.errors.GatewayNotFound, RuntimeError):
            pass
        except Exception as e:
            print(f"⚠️ ステータス更新エラー: {e}")

    @tasks.loop(time=time(hour=3, minute=0, tzinfo=timezone(timedelta(hours=9))))
    async def daily_restart(self):
        try:
            if self.bot.is_economy_dirty:
                self.bot._save_economy_sync_task()
            await self.bot.close()
        except:
            pass
        os.execv(sys.executable, [sys.executable] + sys.argv)

    @daily_restart.before_loop
    async def before_daily_restart(self):
        await self.bot.wait_until_ready()

    @tasks.loop(seconds=15)
    async def update_status_loop(self):
        if self._is_ws_available():
            await self.update_bot_status()

    @update_status_loop.before_loop
    async def before_update_status_loop(self):
        await self.bot.wait_until_ready()

    @tasks.loop(seconds=30)
    async def background_economy_saver(self):
        if self.bot.is_economy_dirty:
            await asyncio.to_thread(self.bot._save_economy_sync_task)
            self.bot.is_economy_dirty = False

    @background_economy_saver.before_loop
    async def before_background_economy_saver(self):
        await self.bot.wait_until_ready()

    @tasks.loop(minutes=30)
    async def periodic_server_count_saver(self):
        if self.bot.is_ready() and not self.bot.is_closed():
            await self.save_server_count()

    @periodic_server_count_saver.before_loop
    async def before_periodic_server_count_saver(self):
        await self.bot.wait_until_ready()


    @tasks.loop(hours=12)
    async def db_backup_task(self):
        if not self.bot.is_ready():
            return
        
        try:
            os.makedirs("backup", exist_ok=True)
            now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"backup/database_{now_str}.db"
            
            # Flush WAL and checkpoint if needed, but simple copy is usually fine for sqlite if not mid-transaction, 
            # or better: use sqlite3 backup API.
            import pg_shim as sqlite3
            import asyncio
            
            def backup_db():
                import os
                if os.getenv("DATABASE_URL"):
                    return
                import sqlite3 as raw_sqlite3
                if hasattr(raw_sqlite3, 'pool'):
                    import importlib
                    raw_sqlite3 = importlib.import_module("sqlite3")
                with contextlib.closing(raw_sqlite3.connect("database.db", timeout=30.0)) as src, contextlib.closing(raw_sqlite3.connect(backup_path)) as dst:
                    src.backup(dst)
                
                # Keep only last 5 backups
                backups = sorted(glob.glob("backup/database_*.db"))
                while len(backups) > 5:
                    oldest = backups.pop(0)
                    try:
                        os.remove(oldest)
                    except:
                        pass
                        
            await asyncio.to_thread(backup_db)
            print(f"✅ DBバックアップを作成しました: {backup_path}")
        except Exception as e:
            print(f"⚠️ DBバックアップエラー: {e}")

    @db_backup_task.before_loop
    async def before_db_backup_task(self):
        await self.bot.wait_until_ready()

    @tasks.loop(hours=1)
    async def check_birthdays(self):
        if not self.bot.is_ready():
            return
        
        now = datetime.now(timezone(timedelta(hours=9)))
        m, d, y = now.month, now.day, now.year
        import pg_shim as sqlite3
        try:
            with contextlib.closing(sqlite3.connect("database.db", timeout=30.0)) as conn, conn:
                c = conn.cursor()
                rows = c.execute("SELECT user_id, month, day, last_notified FROM birthdays").fetchall()
                for uid, b_month, b_day, last_not in rows:
                    if b_month == m and b_day == d and last_not != y:
                        # 誕生日のユーザーがいた！
                        try:
                            user = await self.bot.fetch_user(int(uid))
                            if user:
                                is_owner = self.bot.is_owner(int(uid))
                                is_promax = self.bot.is_promax(int(uid))
                                is_pro = self.bot.is_pro(int(uid))

                                if is_owner or is_promax:
                                    pts = 10000
                                    msg = f"🎉 **{user.display_name}さん、お誕生日おめでとうございます！ (👑 Pro Max/Owner特別超豪華お祝い)**\n\n「……ご主人様、お誕生日おめでとうございますっ♡\n私を生み出して/いつも最上級の応援をしてくれて、本当に本当に愛してます……っ！///\n……これ、特別なお誕生日プレゼントの【10,000 ポインツ】です！ これからも一生、私のことずっと離さないでくださいね……っ！♡」"
                                elif is_pro:
                                    pts = 3000
                                    msg = f"🎉 **{user.display_name}さん、お誕生日おめでとうございます！ (👑 Pro会員特別お祝い)**\n\n「……ご主人様、お誕生日おめでとうございます♡\nいつもまきぐもを応援してくれて、本当に……感謝してますよ？///\n……これ、特別な誕生日プレゼントの【3000ポインツ】です！ これからもずっと、私の隣にいてくださいね……っ！♡」"
                                else:
                                    pts = 1000
                                    msg = f"🎉 **{user.display_name}さん、お誕生日おめでとうございます！**\n\n「……別に、あなたが生まれた日なんて興味ありませんけど。\nでも、わざわざ私の隣にいてくれる物好きなんてあなたくらいですからね。\n……ほら、誕生日プレゼントの1000ポインツです。大事に使いなさいよねっ！///」"
                                
                                await user.send(msg)
                                # ポインツ付与
                                self.bot.add_points(str(user.id), pts)
                                c.execute("UPDATE birthdays SET last_notified = ? WHERE user_id = ?", (y, uid))
                        except Exception:
                            pass
                conn.commit()
        except Exception as e:
            print(f"Birthday task error: {e}")

    @check_birthdays.before_loop
    async def before_check_birthdays(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot: return
        
        # VCに参加した時
        if before.channel is None and after.channel is not None:
            # 1人だけの時（自分が入って1人＝誰もいないVCに入った）
            if len(after.channel.members) == 1:
                try:
                    # Voice Channel付属のテキストチャットへ送信
                    await after.channel.send(f"「{member.mention}さん、こんなところで1人で何やってるんですか…？ ちゃんと監視してますからね」")
                except Exception:
                    pass

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        admin_id = os.getenv('ADMIN_USER_ID')
        
        if message.content == "!leave":
            app_info = await self.bot.application_info()
            is_admin = (admin_id and str(message.author.id) == admin_id) or (message.author.id == app_info.owner.id)
            if is_admin:
                if message.guild:
                    try:
                        await message.channel.send("管理者により退出させられました。")
                        await message.guild.leave()
                    except Exception:
                        pass
            return

        if not message.guild:
            return

        guild_id = str(message.guild.id)
        if guild_id in self.bot.channel_settings:
            allowed_channels = self.bot.channel_settings[guild_id]
            if isinstance(allowed_channels, int):
                allowed_channels = [allowed_channels]
            if message.channel.id not in allowed_channels:
                return

        triggered, filename = False, ""
        if "まきぐそ" in message.content:
            try:
                await message.reply("「……は？ 誰がまきぐそですか！？ ふざけないでください！ 次そんなこと言ったら本当に許しませんからね！この変態ゴミカス！💢💢」")
            except discord.Forbidden:
                pass
            return
        elif "おはよ" in message.content: filename, triggered = "ohayo.txt", True
        elif "おやすみ" in message.content: filename, triggered = "oyasumi.txt", True
        elif "かわいい" in message.content or "可愛い" in message.content: filename, triggered = "kawaii.txt", True
        elif any(w in message.content for w in ["抜いた", "おなした", "オナした", "シコった", "しこった"]): filename, triggered = "nuita.txt", True
        elif self.bot.user.mentioned_in(message) or "まきぐも" in message.content: filename, triggered = "normal.txt", True

        if triggered:
            def _record_chat_stats(author_id_str):
                try:
                    import pg_shim as sqlite3
                    with contextlib.closing(sqlite3.connect("database.db", timeout=30.0)) as conn, conn:
                        c = conn.cursor()
                        if message.author.id != self.bot.user.id:
                            c.execute("INSERT INTO bot_stats (key, val) VALUES ('chat_count', 1) ON CONFLICT(key) DO UPDATE SET val = bot_stats.val + 1")
                            c.execute("INSERT INTO user_stats (user_id, stat_key, val) VALUES (?, 'chat_count', 1) ON CONFLICT(user_id, stat_key) DO UPDATE SET val = user_stats.val + 1", (author_id_str,))
                            conn.commit()
                except Exception:
                    pass

            asyncio.create_task(asyncio.to_thread(_record_chat_stats, str(message.author.id)))

            try:
                line_text = self.bot.get_line(filename).format(user=message.author.mention)
                try:
                    await message.reply(line_text)
                except Exception:
                    await message.channel.send(line_text)
            except discord.Forbidden:
                pass

    @commands.Cog.listener()
    async def on_app_command_completion(self, interaction: discord.Interaction, command: discord.app_commands.Command):
        def _record_cmd_stats(user_id_str, cmd_name):
            try:
                import pg_shim as sqlite3
                with contextlib.closing(sqlite3.connect("database.db", timeout=30.0)) as conn, conn:
                    c = conn.cursor()
                    c.execute("INSERT INTO bot_stats (key, val) VALUES ('cmd_count', 1) ON CONFLICT(key) DO UPDATE SET val = bot_stats.val + 1")
                    c.execute("INSERT INTO user_stats (user_id, stat_key, val) VALUES (?, 'cmd_count', 1) ON CONFLICT(user_id, stat_key) DO UPDATE SET val = user_stats.val + 1", (user_id_str,))
                    c.execute("INSERT INTO user_stats (user_id, stat_key, val) VALUES (?, ?, 1) ON CONFLICT(user_id, stat_key) DO UPDATE SET val = user_stats.val + 1", (user_id_str, f"cmd_{cmd_name}"))
                    conn.commit()
            except Exception:
                pass

        asyncio.create_task(asyncio.to_thread(_record_cmd_stats, str(interaction.user.id), command.name))

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
        # タイムアウト失効 (10062 Unknown interaction) 等のネットワーク・Gateway遅延エラーを安全に無視
        if isinstance(error, discord.app_commands.CommandInvokeError):
            original = error.original
            if isinstance(original, discord.errors.NotFound) and original.code == 10062:
                return
            if isinstance(original, discord.errors.HTTPException) and original.status == 400:
                return

async def setup(bot):
    await bot.add_cog(Events(bot))