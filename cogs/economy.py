import discord
from discord import app_commands
from discord.ext import commands
import random
from datetime import datetime

class ShopView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=180)
        self.bot = bot
        options = []
        if self.bot.shop_items:
            for item_id, item in self.bot.shop_items.items():
                options.append(discord.SelectOption(label=item["name"], description=f"{item['price']} pt", value=item_id))
        else:
            options.append(discord.SelectOption(label="品切れ", value="none"))

        self.select = discord.ui.Select(placeholder="買いたいアイテムを選んでね♡", options=options)
        self.select.callback = self.select_callback
        self.add_item(self.select)

    async def select_callback(self, interaction: discord.Interaction):
        if self.select.values[0] == "none":
            await interaction.response.send_message("品切れです…", ephemeral=True)
            return

        item_id = self.select.values[0]
        item = self.bot.shop_items.get(item_id)
        if not item:
            return await interaction.response.send_message("アイテムが存在しません。", ephemeral=True)

        user_data = self.bot.get_user_data(interaction.user.id)
        if user_data["points"] < item["price"]:
            return await interaction.response.send_message(f"「ポインツが足りないですよ！ あと {item['price'] - user_data['points']} pt 必要です！」", ephemeral=True)

        user_data["points"] -= item["price"]
        inventory = user_data.setdefault("inventory", {})
        inventory[item_id] = inventory.get(item_id, 0) + 1
        self.bot.mark_economy_dirty()

        await interaction.response.send_message(f"「{item['name']}をゲットしました♡ 残り: {user_data['points']} pt」", ephemeral=True)

class UseItemSelect(discord.ui.Select):
    def __init__(self, bot, user_id):
        self.bot = bot
        self.user_id = user_id
        user_data = self.bot.get_user_data(user_id)
        inventory = user_data.get("inventory", {})

        options = []
        consumable_names = {
            "apology_parfait": ("お詫びの高級パフェ", "渡すと機嫌が直って 1000 pt 獲得！"),
            "coffee": ("まきぐも特製コーヒー", "まきぐもと一息つくコーヒーを飲む"),
            "cheat_note": ("カンニングペーパー", "使って 300 pt 獲得！")
        }
        
        for item_id, count in inventory.items():
            if count > 0:
                if item_id in consumable_names:
                    name, desc = consumable_names[item_id]
                    options.append(discord.SelectOption(label=f"{name} (所持: {count})", description=desc[:100], value=item_id))
                elif item_id in self.bot.shop_items:
                    item_info = self.bot.shop_items[item_id]
                    options.append(discord.SelectOption(label=f"{item_info['name']} (所持: {count})", description="装備アイテム（所持で常時発動）", value=item_id))

        if not options:
            options.append(discord.SelectOption(label="使えるアイテムがありません", value="none"))

        super().__init__(placeholder="使いたいアイテムを選んでね♡", options=options)

    async def callback(self, interaction: discord.Interaction):
        item_id = self.values[0]
        if item_id == "none":
            return await interaction.response.send_message("「使えるアイテムを持っていませんよ！」", ephemeral=True)

        user_data = self.bot.get_user_data(interaction.user.id)
        inventory = user_data.get("inventory", {})

        if inventory.get(item_id, 0) <= 0:
            return await interaction.response.send_message("「そのアイテムはもう持っていませんよ！」", ephemeral=True)

        if item_id == "apology_parfait":
            inventory[item_id] -= 1
            user_data["points"] += 1000
            self.bot.mark_economy_dirty()
            await interaction.response.send_message(f"🍨 **お詫びの高級パフェを使用**\n「あむ……んっ、美味しいです♡ まぁ、少しは許してあげなくもないです。（ボーナス 1000 pt もらった！ 現在: {user_data['points']} pt）」", ephemeral=True)

        elif item_id == "coffee":
            inventory[item_id] -= 1
            self.bot.mark_economy_dirty()
            await interaction.response.send_message("☕ **まきぐも特製コーヒーを飲んだ**\n「ほら、熱いから気をつけて飲んでくださいね……？ ふふっ、美味しいですか？♡」", ephemeral=True)

        elif item_id == "cheat_note":
            inventory[item_id] -= 1
            user_data["points"] += 300
            self.bot.mark_economy_dirty()
            await interaction.response.send_message(f"📝 **カンニングペーパーを使用**\n「ふふっ、そんなの見て勉強してるんですか？……可愛いところありますね♡（300 pt ゲット！ 現在: {user_data['points']} pt）」", ephemeral=True)

        else:
            await interaction.response.send_message("「そのアイテムは持っているだけで効果がある装備アイテム（幸運の雲など）ですよ！」", ephemeral=True)

class UseView(discord.ui.View):
    def __init__(self, bot, user_id):
        super().__init__(timeout=180)
        self.add_item(UseItemSelect(bot, user_id))

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="daily", description="1日1回まきぐもから変態ポインツをもらえます")
    async def daily(self, interaction: discord.Interaction):
        await interaction.response.defer()
        user_data = self.bot.get_user_data(interaction.user.id)
        now = datetime.now().timestamp()
        if now - user_data["last_daily"] < 86400:
            left = 86400 - (now - user_data["last_daily"])
            h, m = int(left // 3600), int((left % 3600) // 60)
            return await interaction.followup.send(f"「次は {h}時間{m}分後 ですからね！」", ephemeral=True)

        is_owner = self.bot.is_owner(interaction.user.id)
        is_promax = self.bot.is_promax(interaction.user.id)
        is_pro = self.bot.is_pro(interaction.user.id)

        if is_owner:
            daily_pt = 2000
            msg = f"「開発者様、いつもお疲れ様です♡ 今日の開発費【{daily_pt} pt (Owner特権)】ですよ。現在の所持金は {user_data['points'] + daily_pt} ptです！」"
        else:
            daily_pt = 2000
            msg = f"「ほら、今日の配給【{daily_pt} pt (全機能無料開放ボーナス！)】ですよ♡ 現在の所持金は {user_data['points'] + daily_pt} ptです！」"

        user_data["points"] += daily_pt
        user_data["last_daily"] = now
        self.bot.mark_economy_dirty()
        await interaction.followup.send(msg)

    @app_commands.command(name="gamble", description="まきぐもと変態ポインツを賭けて勝負します（倍率はランダム）")
    async def gamble(self, interaction: discord.Interaction, 賭け金: int):
        await interaction.response.defer()
        user_data = self.bot.get_user_data(interaction.user.id)
        if 賭け金 <= 0 or user_data["points"] < 賭け金:
            return await interaction.followup.send("「ポインツが足りないか、賭け金がおかしいですよ！」", ephemeral=True)

        roll = random.randint(1, 100)
        bonus = self.bot.get_probability_bonus(interaction.user.id)
        # 修正: 上限を90%に統一
        win_threshold = min(90, 40 + int(bonus * 100))

        if roll <= win_threshold:
            user_data["points"] += 賭け金
            bonus_note = f"\n（🎲 幸運補正: +{int(bonus*100)}%）" if bonus > 0 else ""
            msg = f"🎲 **カジノ**\n「ちっ…{interaction.user.mention}さんの勝ちです。{賭け金*2} ptにして返してあげます。」{bonus_note}"
        else:
            user_data["points"] -= 賭け金
            msg = f"🎲 **カジノ**\n「あははっ！ まきぐものの勝ちです！ {賭け金} ptは没収ですからね！」"

        self.bot.mark_economy_dirty()
        await interaction.followup.send(msg)

    @app_commands.command(name="slot", description="変態ポインツを賭けてまきぐもスロットを回します")
    async def slot(self, interaction: discord.Interaction, 賭け金: int):
        await interaction.response.defer()
        user_data = self.bot.get_user_data(interaction.user.id)
        if 賭け金 <= 0 or user_data["points"] < 賭け金:
            return await interaction.followup.send("「賭け金が足りないですよ？」", ephemeral=True)

        user_data["points"] -= 賭け金
        symbols = ["🍒", "🍇", "🍉", "💖", "💡"]
        bonus = self.bot.get_probability_bonus(interaction.user.id)

        if bonus > 0 and random.random() < bonus:
            target = random.choice(symbols)
            res = [target, target, target]
        else:
            res = [random.choice(symbols) for _ in range(3)]

        if res[0] == res[1] == res[2]:
            if res[0] == "💖": winnings, msg = 賭け金 * 10, f"「えっ、大・大・大当り……！？ {賭け金*10} ptあげます！」"
            elif res[0] == "💡": winnings, msg = 0, f"「怒りマークが揃いました！ お仕置き確定です！ 没収！」"
            else: winnings, msg = 賭け金 * 3, f"「当たりですね。{賭け金*3} pt返してあげます。」"
        elif res[0] == res[1] or res[1] == res[2] or res[0] == res[2]:
            winnings, msg = int(賭け金 * 1.5), f"「小当たりですね。{int(賭け金 * 1.5)} ptです。」"
        else:
            winnings, msg = 0, f"「ハズレです！ {賭け金} ptいただきまーーす！」"

        user_data["points"] += winnings
        self.bot.mark_economy_dirty()

        embed = discord.Embed(title="まきぐもスロット", color=0xffb6c1)
        embed.add_field(name="結果", value=f"**[ {res[0]} | {res[1]} | {res[2]} ]**", inline=False)
        embed.add_field(name="一言", value=msg, inline=False)
        embed.set_footer(text=f"所持金: {user_data['points']} pt" + (f" | 幸運補正: +{int(bonus*100)}%" if bonus > 0 else ""))
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="shop", description="ポインツでアイテムを購入できます")
    async def shop(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not self.bot.shop_items:
            return await interaction.followup.send("「ショップがまだ空っぽです…」", ephemeral=True)

        embed = discord.Embed(title="🛍️ まきぐも特製ショップ", description="ポインツを使ってアイテムを購入できるよ♡", color=0xffb6c1)
        for item_id, item in self.bot.shop_items.items():
            b = item.get("probability_bonus", 0)
            b_txt = f"\n🎲 ギャンブル勝率 +{b*100:.0f}%" if b > 0 else ""
            embed.add_field(name=f"{item['name']}", value=f"{item['description']}{b_txt}\n💰 {item['price']} pt", inline=False)

        await interaction.followup.send(embed=embed, view=ShopView(self.bot), ephemeral=True)

    @app_commands.command(name="work", description="まきぐものお手伝いをしてポインツを稼ぎます（3時間に1回）")
    async def work(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        user_data = self.bot.get_user_data(interaction.user.id)
        now = datetime.now().timestamp()

        last_work = user_data.get("last_work", 0)
        if now - last_work < 10800:
            left = 10800 - (now - last_work)
            h, m = int(left // 3600), int((left % 3600) // 60)
            return await interaction.followup.send(f"「さっき働いたばかりじゃないですか！次は {h}時間{m}分後 です！」", ephemeral=True)

        user_data["last_work"] = now

        scenarios = [
            {"msg": "まきぐもの肩たたきをしてあげました。「んっ…そこ、気持ちいいです……」", "pt": 300},
            {"msg": "まきぐもの代わりにお茶を淹れました。「ふふっ、ありがとうございます。美味しいです♡」", "pt": 200},
            {"msg": "まきぐもと一緒に監視業務を手伝いました。「…っ、変なところ見ないでください！」", "pt": 400},
            {"msg": "まきぐものお部屋の掃除をしました。「勝手に触らないでって言いましたよね！？ 罰金です！」", "pt": -100}
        ]

        scenario = random.choice(scenarios)
        user_data["points"] += scenario["pt"]
        if user_data["points"] < 0:
            user_data["points"] = 0

        self.bot.mark_economy_dirty()

        action_text = "獲得" if scenario["pt"] > 0 else "没収"
        pt_abs = abs(scenario["pt"])
        await interaction.followup.send(f"🧹 **アルバイト**\n{scenario['msg']}\n\n(💰 {pt_abs} pt {action_text}！ 現在: {user_data['points']} pt)", ephemeral=True)

    @app_commands.command(name="pay", description="他の変態さんにポインツを貢ぎます（送金）")
    async def pay(self, interaction: discord.Interaction, 相手: discord.Member, 額: int):
        await interaction.response.defer()
        if 額 <= 0:
            return await interaction.followup.send("「1pt以上じゃないと送れませんよ！」", ephemeral=True)
        if 相手.bot:
            return await interaction.followup.send("「Botに貢いでどうするんですか……私にください！」", ephemeral=True)
        if 相手.id == interaction.user.id:
            return await interaction.followup.send("「自分に送ってどうするんですか？ 虚しくないですか？」", ephemeral=True)

        sender_data = self.bot.get_user_data(interaction.user.id)
        if sender_data["points"] < 額:
            return await interaction.followup.send("「ポインツが足りないですよ！ 見栄を張らないでください！」", ephemeral=True)

        receiver_data = self.bot.get_user_data(相手.id)

        sender_data["points"] -= 額
        receiver_data["points"] += 額
        self.bot.mark_economy_dirty()

        await interaction.followup.send(f"💸 **送金完了**\n「{interaction.user.mention}さんが、{相手.mention}さんに {額} pt 貢ぎましたよ！ 何を企んでるんですか…？」")

    @app_commands.command(name="ranking", description="各種変態ランキングトップ10を表示します")
    @app_commands.choices(種類=[
        app_commands.Choice(name="💰 所持ポインツ長者番付", value="points"),
        app_commands.Choice(name="💬 AI対話回数ランキング", value="ai"),
        app_commands.Choice(name="⚡ コマンド実行数ランキング", value="cmd"),
        app_commands.Choice(name="🎁 まきぐもへのお貢ぎランキング", value="present"),
        app_commands.Choice(name="📊 レベルランキング", value="level"),
    ])
    async def ranking(self, interaction: discord.Interaction, 種類: app_commands.Choice[str] = None):
        await interaction.response.defer()
        rank_type = 種類.value if 種類 else "points"
        import pg_shim as sqlite3

        items = []
        unit = "pt"
        title = "🏆 変態長者番付トップ10"
        desc_header = "現在最もポインツを貯め込んでいる変態さんたちです♡"

        if rank_type == "points":
            sorted_users = sorted(self.bot.economy.items(), key=lambda x: x[1].get("points", 0), reverse=True)
            for uid, data in sorted_users:
                pts = data.get("points", 0)
                if pts > 0: items.append((uid, pts))
            unit = "pt"
        elif rank_type in ["ai", "cmd", "present"]:
            sk_map = {"ai": ("ai_count", "💬 AI対話回数ランキングトップ10", "回"),
                      "cmd": ("cmd_count", "⚡ コマンド実行数ランキングトップ10", "回"),
                      "present": ("present_count", "🎁 まきぐもへのお貢ぎランキングトップ10", "回")}
            sk, title, unit = sk_map[rank_type]
            desc_header = f"現在最も{sk_map[rank_type][1].replace('トップ10', '')}が多い変態さんたちです♡"
            try:
                with contextlib.closing(sqlite3.connect("database.db", timeout=30.0)) as conn, conn:
                    c = conn.cursor()
                    rows = c.execute("SELECT user_id, val FROM user_stats WHERE stat_key = ? ORDER BY val DESC LIMIT 10", (sk,)).fetchall()
                    for r in rows:
                        if r[1] > 0: items.append((r[0], r[1]))
            except Exception:
                pass
        elif rank_type == "level":
            title = "📊 変態レベルランキングトップ10"
            desc_header = "現在最もレベルとXPが高い変態さんたちです♡"
            unit = "Lv"
            try:
                with contextlib.closing(sqlite3.connect("database.db", timeout=30.0)) as conn, conn:
                    c = conn.cursor()
                    rows = c.execute("SELECT user_id, level, xp FROM levels ORDER BY level DESC, xp DESC LIMIT 10").fetchall()
                    for r in rows:
                        items.append((r[0], f"Lv.{r[1]} (`{r[2]} XP`)"))
            except Exception:
                pass

        embed = discord.Embed(title=title, description=desc_header, color=0xffd700)
        desc = ""
        for i, item in enumerate(items[:10]):
            uid = item[0]
            val_str = f"**{item[1]}** {unit}" if rank_type != "level" else item[1]
            medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"**{i+1}位**"
            desc += f"{medal} <@{uid}> : {val_str}\n"

        if not desc:
            desc = "まだランキングデータがありません。"

        embed.description = desc
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="use", description="所持しているアイテムをメニューから選んで使います")
    async def use(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        user_data = self.bot.get_user_data(interaction.user.id)
        inventory = user_data.get("inventory", {})

        has_any = any(count > 0 for count in inventory.values())
        if not has_any:
            return await interaction.followup.send("「アイテムを何も持っていませんよ！ `/shop` でお買い物してきてくださいね♡」", ephemeral=True)

        embed = discord.Embed(title="🎒 アイテムを使う", description="下のメニューから使いたいアイテムを選んでくださいね♡", color=0xffb6c1)
        await interaction.followup.send(embed=embed, view=UseView(self.bot, interaction.user.id), ephemeral=True)

    @app_commands.command(name="stats", description="あなたの変態カルテ（レベル・ポインツ・勝率・AI対話数・所持アイテム）を確認します")
    async def stats(self, interaction: discord.Interaction, ターゲット: discord.Member = None):
        await interaction.response.defer()
        target_user = ターゲット or interaction.user
        user_id = str(target_user.id)
        
        user_data = self.bot.get_user_data(user_id)
        points = user_data.get("points", 0)
        inventory = user_data.get("inventory", {})
        bonus = self.bot.get_probability_bonus(target_user.id)

        lvl_info = getattr(self.bot, 'levels', {}).get(user_id, {"xp": 0, "level": 1})
        lvl = lvl_info.get("level", 1)
        xp = lvl_info.get("xp", 0)

        ai_count, cmd_count, present_count = 0, 0, 0
        equipped_title = None
        import pg_shim as sqlite3
        try:
            with contextlib.closing(sqlite3.connect("database.db", timeout=30.0)) as conn, conn:
                c = conn.cursor()
                for row in c.execute("SELECT stat_key, val FROM user_stats WHERE user_id = ?", (user_id,)):
                    sk, v = row[0], row[1]
                    if sk == "ai_count": ai_count = v
                    elif sk == "cmd_count": cmd_count = v
                    elif sk == "present_count": present_count = v
                
                row = c.execute("SELECT equipped_title FROM user_titles WHERE user_id = ?", (user_id,)).fetchone()
                if row: equipped_title = row[0]
        except Exception:
            pass

        # 称号が未設定の場合のデフォルト称号計算（レベルに応じた最高称号を適用）
        if not equipped_title:
            if lvl >= 300: equipped_title = "👑💎🌌 【天上天下唯我独尊・変態創世神】"
            elif lvl >= 280: equipped_title = "🔱 神をも恐れぬ究極変態"
            elif lvl >= 260: equipped_title = "⚜️ まきぐも狂愛の化身"
            elif lvl >= 240: equipped_title = "🌌✨ 銀河系最終変態兵器"
            elif lvl >= 220: equipped_title = "💫 時空超越のドM"
            elif lvl >= 200: equipped_title = "👑✨ 【変態界の絶対君主】"
            elif lvl >= 180: equipped_title = "🐉 変態神龍"
            elif lvl >= 160: equipped_title = "🩸 快楽狂気のエクスタシー"
            elif lvl >= 140: equipped_title = "🪐 惑星破壊級ド変態"
            elif lvl >= 120: equipped_title = "🌪️ 欲望の暴風雨"
            elif lvl >= 100: equipped_title = "🌟 【百変態神】"
            elif lvl >= 90: equipped_title = "⚔️ 神域のドM戦士"
            elif lvl >= 80: equipped_title = "💎 変態大公爵"
            elif lvl >= 70: equipped_title = "🔮 変態深淵の探究者"
            elif lvl >= 60: equipped_title = "😈 淫靡なる支配者"
            elif lvl >= 50: equipped_title = "👑 伝説の変態"
            elif lvl >= 40: equipped_title = "💀 快楽の亡者"
            elif lvl >= 30: equipped_title = "🌌 宇宙規模の変態"
            elif lvl >= 20: equipped_title = "⚡ 覚醒せし変態"
            elif lvl >= 10: equipped_title = "🔥 真なるドM"
            elif lvl >= 5: equipped_title = "🔰 見習い変態"
            else:
                total_act = ai_count + cmd_count
                if total_act >= 150: equipped_title = "👑 伝説の変態皇帝"
                elif total_act >= 80: equipped_title = "💎 ど変態マスター"
                elif total_act >= 30: equipped_title = "✨ 熟練の変態さん"
                elif total_act >= 10: equipped_title = "🔰 一人前の変態"
                else: equipped_title = "🌱 ひよっこ変態見習い"

        win_rate = min(90, 40 + int(bonus * 100))

        is_owner = self.bot.is_owner(target_user.id)
        is_promax = self.bot.is_promax(target_user.id)
        is_pro = self.bot.is_pro(target_user.id)

        user_plan = self.bot.get_user_plan(target_user.id)
        if is_owner:
            color = 0xFF4500
            title_prefix = "OWNER "
            status_text = "`OWNER (開発者)`"
        elif 'promax' in user_plan:
            color = 0xE5E4E2
            title_prefix = "筆頭パトロン "
            status_text = "`筆頭パトロン (特別支援者)`"
        elif 'pro' in user_plan:
            color = 0xFFD700
            title_prefix = "パトロン "
            status_text = "`まきぐもパトロン (支援者)`"
        else:
            color = 0x9370db
            title_prefix = ""
            status_text = "`一般ユーザー`"

        embed = discord.Embed(title=f"{title_prefix}ステータス - {target_user.display_name}", color=color)
        if target_user.display_avatar:
            embed.set_thumbnail(url=target_user.display_avatar.url)

        if status_text:
            embed.add_field(name="会員ステータス", value=status_text, inline=False)

        embed.add_field(name="称号", value=f"**{equipped_title}**", inline=False)
        embed.add_field(name="レベル & XP", value=f"**Lv.{lvl}** (`{xp} XP`)", inline=True)
        embed.add_field(name="所持ポインツ", value=f"**{points}** pts", inline=True)
        embed.add_field(name="ギャンブル勝率", value=f"**{win_rate}%** *(補正 +{int(bonus*100)}%)*", inline=True)

        embed.add_field(name="AI対話回数", value=f"**{ai_count}** 回", inline=True)
        embed.add_field(name="コマンド実行数", value=f"**{cmd_count}** 回", inline=True)
        embed.add_field(name="お貢ぎ数", value=f"**{present_count}** 回", inline=True)

        inv_text = ""
        for item_id, count in inventory.items():
            if count > 0:
                item_name = self.bot.shop_items.get(item_id, {}).get("name", "謎のアイテム")
                inv_text += f"・{item_name} × {count}\n"

        if not inv_text:
            inv_text = "何も持っていません。"

        embed.add_field(name="🎒 所持アイテム", value=inv_text, inline=False)
        embed.set_footer(text="まきぐもぼっとがあなたの変態行為を24時間監視中♡")

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="titles", description="解放した称号を確認し、装備します")
    async def titles(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        user_id = str(interaction.user.id)
        is_owner = self.bot.is_owner(user_id)
        is_promax = self.bot.is_promax(user_id)
        is_pro = self.bot.is_pro(user_id)
        
        lvl_info = getattr(self.bot, 'levels', {}).get(user_id, {"level": 1})
        lvl = lvl_info.get("level", 1)
        
        ai_count, cmd_count, present_count = 0, 0, 0
        import pg_shim as sqlite3
        try:
            with contextlib.closing(sqlite3.connect("database.db", timeout=30.0)) as conn, conn:
                c = conn.cursor()
                for row in c.execute("SELECT stat_key, val FROM user_stats WHERE user_id = ?", (user_id,)):
                    sk, v = row[0], row[1]
                    if sk == "ai_count": ai_count = v
                    elif sk == "cmd_count": cmd_count = v
                    elif sk == "present_count": present_count = v
        except Exception:
            pass

        total_act = ai_count + cmd_count
        unlocked = ["🌱 ひよっこ変態見習い"]
        if total_act >= 10: unlocked.append("🔰 一人前の変態")
        if total_act >= 30: unlocked.append("✨ 熟練の変態さん")
        if total_act >= 80: unlocked.append("💎 ど変態マスター")
        if total_act >= 150: unlocked.append("👑 伝説の変態皇帝")
        
        # レベル称号 (Lv.5 〜 Lv.300)
        level_titles = [
            (5, "🔰 見習い変態"),
            (10, "🔥 真なるドM"),
            (20, "⚡ 覚醒せし変態"),
            (30, "🌌 宇宙規模の変態"),
            (40, "💀 快楽の亡者"),
            (50, "👑 伝説の変態"),
            (60, "😈 淫靡なる支配者"),
            (70, "🔮 変態深淵の探究者"),
            (80, "💎 変態大公爵"),
            (90, "⚔️ 神域のドM戦士"),
            (100, "🌟 【百変態神】"),
            (120, "🌪️ 欲望の暴風雨"),
            (140, "🪐 惑星破壊級ド変態"),
            (160, "🩸 快楽狂気のエクスタシー"),
            (180, "🐉 変態神龍"),
            (200, "👑✨ 【変態界の絶対君主】"),
            (220, "💫 時空超越のドM"),
            (240, "🌌✨ 銀河系最終変態兵器"),
            (260, "⚜️ まきぐも狂愛の化身"),
            (280, "🔱 神をも恐れぬ究極変態"),
            (300, "👑💎🌌 【天上天下唯我独尊・変態創世神】"),
        ]
        for req_lvl, t_name in level_titles:
            if lvl >= req_lvl and t_name not in unlocked:
                unlocked.append(t_name)

        if present_count >= 10: unlocked.append("💸 上客パパ活おぢさん")
        if present_count >= 50: unlocked.append("💍 まきぐものATM")

        # Pro / Pro Max / Owner限定称号
        if is_pro or is_promax or is_owner:
            unlocked.append("👑 まきぐもパトロン")
            unlocked.append("💎 筆頭変態紳士")

        if is_promax or is_owner:
            unlocked.append("🌌 宇宙の覇王")
            unlocked.append("💖 まきぐもの愛人")
            unlocked.append("👑 超絶富豪パトロン")

        if is_owner:
            unlocked.append("👑 まきぐも創造主")
            unlocked.append("⚡ 絶対神")

        # Discordのセレクトメニュー制限 (最大25件) に配慮して上位25件を表示
        display_unlocked = unlocked[-25:] if len(unlocked) > 25 else unlocked
        options = [discord.SelectOption(label=t, value=t) for t in display_unlocked]
        
        class TitleSelect(discord.ui.Select):
            def __init__(self):
                super().__init__(placeholder="装備する称号を選んでください", min_values=1, max_values=1, options=options)
            
            async def callback(self, interact: discord.Interaction):
                selected = self.values[0]
                try:
                    with contextlib.closing(sqlite3.connect("database.db", timeout=30.0)) as conn, conn:
                        cu = conn.cursor()
                        cu.execute("INSERT OR REPLACE INTO user_titles (user_id, equipped_title) VALUES (?, ?)", (str(interact.user.id), selected))
                        conn.commit()
                    await interact.response.send_message(f"✅ 称号を **{selected}** に変更しました！\n`/stats` で確認してみましょう♡", ephemeral=True)
                except Exception as e:
                    await interact.response.send_message(f"❌ 変更に失敗しました: {e}", ephemeral=True)

        class TitleView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=60)
                self.add_item(TitleSelect())
                
        desc = "**【現在解放済みの称号】**\n" + "\n".join(f"・{t}" for t in unlocked) + "\n\n下のメニューから装備したい称号を選んでください！"
        embed = discord.Embed(title="🎖️ 変態称号の管理", description=desc, color=0x9932cc)
        await interaction.followup.send(embed=embed, view=TitleView(), ephemeral=True)

async def setup(bot):
    await bot.add_cog(Economy(bot))