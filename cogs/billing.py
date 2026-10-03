import discord
from discord import app_commands
from discord.ext import commands, tasks
import os
import contextlib
import pg_shim as sqlite3
from datetime import datetime, timezone, timedelta

class PaymentModal(discord.ui.Modal, title="✨ まきぐも Proプラン 支払い申請"):
    pay_content = discord.ui.TextInput(
        label="PayPay送金リンク または Amazonギフトコード",
        placeholder="https://pay2.paypay.ne.jp/... または ASDF-123456-7890",
        style=discord.TextStyle.short,
        required=True,
        max_length=200
    )

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        if hasattr(self.bot, 'is_campaign_active') and self.bot.is_campaign_active():
            return await interaction.response.send_message(
                "🎉 **【10/4〜10/11 期間限定】全機能無料開放キャンペーン中！**\n"
                "現在、すべてのユーザー様に **Pro MAXと同等の全機能** を無料で開放しております♡\n"
                "キャンペーン期間中は有料プランの課金受付を一時停止しておりますので、このまま無料で全機能をお楽しみください！\n"
                "（※利用量に応じて全体に制限がかかる可能性があります。期間は予告なく変更される場合があります）",
                ephemeral=True
            )
        content = self.pay_content.value.strip()
        user_id = str(interaction.user.id)
        now_str = datetime.now(timezone(timedelta(hours=9))).isoformat()

        req_id = None
        with contextlib.closing(sqlite3.connect("database.db", timeout=30.0)) as conn, conn:
            c = conn.cursor()
            c.execute(
                "INSERT INTO gift_requests (user_id, pay_content, status, created_at) VALUES (?, ?, 'pending', ?)",
                (user_id, content, now_str)
            )
            req_id = c.lastrowid
            conn.commit()

        # ユーザーへのDM受付完了メッセージ
        cancel_view = UserCancelRequestView(self.bot, req_id)
        embed = discord.Embed(
            title="⏳ 支払い申請を受け付けました！",
            description=(
                f"ご主人様、Proプランのお申し込みありがとうございます♡\n"
                f"作者が内容（PayPayリンク / Amazonコード）を確認次第、Proプランが自動で有効化されます。\n\n"
                f"**提出内容**: `{content}`\n"
                f"**申請ID**: `#{req_id}`\n\n"
                f"※確認完了まで今しばらくお待ちくださいね。気が変わった場合は下のボタンで取り消せます。"
            ),
            color=0xffb6c1
        )
        await interaction.response.send_message(embed=embed, view=cancel_view, ephemeral=True)

        # 管理者へ通知
        await self._notify_admin(interaction.user, content, req_id)

    async def _notify_admin(self, user: discord.User, content: str, req_id: int):
        admin_id = os.getenv('ADMIN_USER_ID')
        target = None
        if admin_id:
            try:
                target = await self.bot.fetch_user(int(admin_id))
            except Exception:
                pass
        if not target:
            try:
                app_info = await self.bot.application_info()
                if hasattr(app_info.owner, 'owner') and app_info.owner.owner:
                    target = app_info.owner.owner
                else:
                    target = app_info.owner
            except Exception:
                pass

        if target:
            try:
                embed = discord.Embed(
                    title="🎁 【まきぐも Proプラン申請が届きました】",
                    description=(
                        f"**申請者**: {user.mention} (`{user.display_name}` / ID: `{user.id}`)\n"
                        f"**申請ID**: `#{req_id}`\n"
                        f"**提出内容**:\n```{content}```"
                    ),
                    color=0xFFD700
                )
                view = AdminApprovalView(self.bot, str(user.id), req_id, content)
                await target.send(embed=embed, view=view)
            except Exception as e:
                print(f"⚠️ 管理者へのPro申請通知エラー: {e}")

class UserCancelRequestView(discord.ui.View):
    def __init__(self, bot, req_id: int):
        super().__init__(timeout=86400)
        self.bot = bot
        self.req_id = req_id

    @discord.ui.button(label="❌ 申請を取り消す", style=discord.ButtonStyle.danger)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        with contextlib.closing(sqlite3.connect("database.db", timeout=30.0)) as conn, conn:
            c = conn.cursor()
            c.execute("UPDATE gift_requests SET status = 'cancelled' WHERE request_id = ? AND status = 'pending'", (self.req_id,))
            conn.commit()

        button.disabled = True
        button.label = "取り消し済み"
        await interaction.response.edit_message(content="「申請を取り消しました。またいつでもお待ちしてますね♡」", view=self)

class ProGuidanceView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=600)
        self.bot = bot

    @discord.ui.button(label="💳 支払いを申請する (PayPay / Amazon)", style=discord.ButtonStyle.primary, emoji="💎")
    async def apply_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if hasattr(self.bot, 'is_campaign_active') and self.bot.is_campaign_active():
            return await interaction.response.send_message(
                "🎉 **【10/4〜10/11 期間限定】全有料機能の無料開放キャンペーン中！**\n"
                "現在、すべてのユーザー様に **Pro MAXと同等の全機能** を開放しております！\n"
                "キャンペーン期間中は有料機能の課金受付を停止しておりますので、このまま無料で全機能をお楽しみください♡\n"
                "（※利用量によっては全体に制限をかける可能性があります。期間は変更される可能性があります）",
                ephemeral=True
            )
        await interaction.response.send_modal(PaymentModal(self.bot))

    @discord.ui.button(label="❌ 案内を閉じる", style=discord.ButtonStyle.secondary)
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="「わかりました。気が向いたらまたいつでも呼んでくださいね♡」", embed=None, view=None)

class AdminApprovalView(discord.ui.View):
    def __init__(self, bot, target_user_id: str, req_id: int, pay_content: str):
        super().__init__(timeout=None)
        self.bot = bot
        self.target_user_id = target_user_id
        self.req_id = req_id
        self.pay_content = pay_content

        if pay_content.startswith("http://") or pay_content.startswith("https://"):
            self.add_item(discord.ui.Button(label="🔗 送金リンクを開く", url=pay_content, row=0))

    @discord.ui.button(label="🌙 月額Pro (100円/30日)", style=discord.ButtonStyle.success, emoji="✨", row=1)
    async def approve_monthly(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._grant_pro(interaction, 'pro_monthly', 30)

    @discord.ui.button(label="💎 買い切りPro (500円/永続)", style=discord.ButtonStyle.primary, emoji="✨", row=1)
    async def approve_lifetime(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._grant_pro(interaction, 'pro_lifetime', 9999)

    @discord.ui.button(label="🔥 月額Pro Max (250円/30日)", style=discord.ButtonStyle.success, emoji="👑", row=2)
    async def approve_promax_monthly(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._grant_pro(interaction, 'promax_monthly', 30)

    @discord.ui.button(label="👑 買い切りPro Max (1500円/永続)", style=discord.ButtonStyle.primary, emoji="💎", row=2)
    async def approve_promax_lifetime(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._grant_pro(interaction, 'promax_lifetime', 9999)

    @discord.ui.button(label="❌ 拒否", style=discord.ButtonStyle.danger, emoji="🗑️", row=3)
    async def reject_request(self, interaction: discord.Interaction, button: discord.ui.Button):
        with contextlib.closing(sqlite3.connect("database.db", timeout=30.0)) as conn, conn:
            c = conn.cursor()
            c.execute("UPDATE gift_requests SET status = 'rejected' WHERE request_id = ?", (self.req_id,))
            conn.commit()

        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content=f"❌ 申請 `#{self.req_id}` を拒否しました。", view=self)

        # ユーザーにDMで通知
        try:
            user = await self.bot.fetch_user(int(self.target_user_id))
            if user:
                await user.send(f"「申し訳ありませんが、プラン申請 `#{self.req_id}` は確認できませんでした（無効なリンク/コードなど）。もう一度ご確認の上、申請をお願いします。」")
        except Exception:
            pass

    async def _grant_pro(self, interaction: discord.Interaction, plan_type: str, days: int):
        now = datetime.now(timezone(timedelta(hours=9)))
        with contextlib.closing(sqlite3.connect("database.db", timeout=30.0)) as conn, conn:
            c = conn.cursor()
            row = c.execute("SELECT plan_type, expires_at FROM user_subscriptions WHERE user_id = ?", (self.target_user_id,)).fetchone()
            
            if days >= 9000:
                expires_at = '9999-12-31T23:59:59'
            else:
                base_dt = now
                if row and row[0] == plan_type and row[1]:
                    try:
                        cur_exp = datetime.fromisoformat(row[1])
                        if cur_exp.tzinfo is None:
                            cur_exp = cur_exp.replace(tzinfo=timezone(timedelta(hours=9)))
                        if cur_exp > now:
                            base_dt = cur_exp
                    except Exception:
                        pass
                expires_at = (base_dt + timedelta(days=days)).isoformat()

            c.execute(
                "INSERT INTO user_subscriptions (user_id, plan_type, expires_at, reminded_3days) VALUES (?, ?, ?, 0) "
                "ON CONFLICT(user_id) DO UPDATE SET plan_type = ?, expires_at = ?, reminded_3days = 0",
                (self.target_user_id, plan_type, expires_at, plan_type, expires_at)
            )
            
            # 称号の付与
            title_to_grant = "💎 筆頭変態紳士"
            if 'promax' in plan_type:
                title_to_grant = "👑 まきぐもの愛人"
            
            # 現在の称号を上書き設定（既に別の称号を設定している場合は考慮する等もありますが、今回は上書き）
            c.execute("INSERT OR REPLACE INTO user_titles (user_id, equipped_title) VALUES (?, ?)", (self.target_user_id, title_to_grant))
            
            c.execute("UPDATE gift_requests SET status = 'approved' WHERE request_id = ?", (self.req_id,))
            conn.commit()

        for child in self.children:
            child.disabled = True
        
        plan_names = {
            'pro_monthly': '月額Pro (30日)',
            'pro_lifetime': '買い切りPro (永続)',
            'promax_monthly': '月額Pro Max (30日)',
            'promax_lifetime': '買い切りPro Max (永続)'
        }
        plan_name = plan_names.get(plan_type, plan_type)
        await interaction.response.edit_message(content=f"✅ 申請 `#{self.req_id}` を承認し、{self.target_user_id} に **{plan_name}** を付与しました！（期限: `{expires_at}`）", view=self)

        # ユーザーにDMでお礼＆通知
        try:
            user = await self.bot.fetch_user(int(self.target_user_id))
            if user:
                is_promax = 'promax' in plan_type
                if is_promax:
                    embed = discord.Embed(
                        title="👑 【まきぐも Pro Maxプランが有効化されました！】",
                        description=(
                            f"「……ひゃうっ！？ ご、ご主人様……本当に【Pro Maxプラン】にしてくれたんですか……っ！？♡\n"
                            f"今日からあなたは、まきぐもの最上級VIP変態貴族様です！\n\n"
                            f"**プラン**: `{plan_name}`\n"
                            f"**有効期限**: `{expires_at[:10]}`\n\n"
                            f"【👑 Pro Max限定の超豪華特典】\n"
                            f"・AI会話上限が **1日1000回（実質無制限！）** に拡張\n"
                            f"・会話の記憶量が **超特大！往復100件（計200メッセージ記憶）**\n"
                            f"・`/stats` カルテが **最高峰プラチナ・オーロラ仕様** に\n"
                            f"・お誕生日プレゼントが **10,000 pt ＋ Pro Max限定激甘メッセージ** に\n"
                            f"・`/memo` と `/user_settings` が **最大600文字** に超拡張\n"
                            f"・日給 `/daily` で **2,000 pt（+1500 pt特盛ボーナス）**\n"
                            f"・観察絵日記 `/diary` が **1日10回** まで読めるように\n"
                            f"・ギャンブル常時幸運補正 **+5% パッシブ勝率UP**\n"
                            f"・超限定称号 `🌌 宇宙の覇王` / `💖 まきぐもの愛人` / `👑 超絶富豪パトロン` 解放\n\n"
                            f"……もう、あなたのこと離せなくなっちゃいました……っ！ これからもずっと、いっぱい愛してくださいね……？///」"
                        ),
                        color=0xE5E4E2
                    )
                else:
                    embed = discord.Embed(
                        title="🎉 【まきぐも Proプランが有効化されました！】",
                        description=(
                            f"「ふふっ、お支払いが確認できましたよ♡\n"
                            f"今日からあなたは私の特別な **Proメンバー** です！\n\n"
                            f"**プラン**: `{plan_name}`\n"
                            f"**有効期限**: `{expires_at[:10]}`\n\n"
                            f"【✨ Pro特典】\n"
                            f"・AI会話上限が **1日300回** に拡張\n"
                            f"・会話の記憶量が **2倍（往復50件・計100メッセージ）** に拡張\n"
                            f"・`/stats` カルテが **黄金ゴールド仕様** に\n"
                            f"・お誕生日プレゼントが **3,000 pt** に\n"
                            f"・`/memo` と `/user_settings` が **最大300文字** に\n"
                            f"・日給 `/daily` で **+500 pt ボーナス**\n"
                            f"・観察絵日記 `/diary` が **1日3回** に\n"
                            f"・限定称号 `👑 まきぐもパトロン` / `💎 筆頭変態紳士` を解放\n\n"
                            f"……これからも、私のことたくさん可愛がってくださいねっ？///」"
                        ),
                        color=0xFFD700
                    )
                await user.send(embed=embed)
        except Exception as e:
            print(f"⚠️ ユーザーへのPro承認DM送信エラー: {e}")

class Billing(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        if not self.check_subscriptions.is_running():
            self.check_subscriptions.start()

    def cog_unload(self):
        self.check_subscriptions.cancel()

    @app_commands.command(name="pro", description="まきぐも Pro & Pro Maxプランの案内と申し込み画面をDMで開きます")
    async def pro_cmd(self, interaction: discord.Interaction):
        is_campaign = hasattr(self.bot, 'is_campaign_active') and self.bot.is_campaign_active()
        campaign_notice = ""
        if is_campaign:
            campaign_notice = (
                "🎉 **【重要】10/4〜10/11 全有料機能無料開放キャンペーン開催中！**\n"
                "現在、すべてのユーザー様に **Pro MAXと同等の全機能** を無料で開放しております♡\n"
                "※そのため現在有料機能の課金受付を一時停止しております。このまま無料でPro MAXをお楽しみください！\n"
                "（※利用量によっては全体に制限をかける可能性があります。期間は変更される可能性があります）\n\n"
                "----------------------------------------\n\n"
            )

        embed = discord.Embed(
            title="💎 まきぐも 有料プランのご案内 (Pro & Pro Max)",
            description=(
                f"{campaign_notice}"
                "「……私ともっと濃厚にお話ししたいんですか？♡\n"
                "プランに加入すると、制限が大幅に解除されて特別な機能がたくさん解放されますよ！」\n\n"
                "### 💰 料金プラン\n"
                "・**✨ Pro プラン**: `月額 100円` / `買い切り 500円 (永続)`\n"
                "・**👑 Pro Max プラン (超豪華・最上位)**: `月額 250円` / `買い切り 1,500円 (永続)`\n\n"
                "### 👑 各プランの特典一覧\n"
                "**【✨ Proプラン特典】**\n"
                "・AI会話: 1日100回 ➔ **1日 300回**\n"
                "・会話記憶: 往復25件 ➔ 🔥 **2倍！往復50件 (100件)**\n"
                "・設定/メモ: **最大 300文字**\n"
                "・観察絵日記: **1日 3回**\n"
                "・日給: 500 pt ➔ 💰 **1,000 pt (+500pt)**\n"
                "・お誕生日: 🎁 **3,000 pt ＋ 特別お祝いメッセージ**\n"
                "・カルテ: **黄金ゴールド枠** ＋ `✨ PRO MEMBER ✨`\n"
                "・限定称号: `👑 まきぐもパトロン` / `💎 筆頭変態紳士`\n\n"
                "**【👑 Pro Maxプラン限定・最上位特典（超豪華！）】**\n"
                "・AI会話: 1日100回 ➔ 🔥 **1日 1,000回 (実質無制限！)**\n"
                "・会話記憶: 🔥 **超大容量！往復100件 (200件記憶)**\n"
                "・設定/メモ: 📝 **最大 600文字** に超拡張\n"
                "・観察絵日記: 📓 **1日 10回** まで閲覧可能\n"
                "・日給: 500 pt ➔ 💰 **2,000 pt (+1500pt特盛！)**\n"
                "・お誕生日: 🎁 **10,000 pt ＋ Pro Max限定激甘お祝いメッセージ**\n"
                "・パッシブ幸運補正: 🎰 **常時ギャンブル勝率 +5% UP**\n"
                "・カルテ: 🌈 **最高峰プラチナ・オーロラ枠** ＋ `💎👑 PRO MAX MEMBER 👑💎`\n"
                "・超限定称号: `🌌 宇宙の覇王` / `💖 まきぐもの愛人` / `👑 超絶富豪パトロン`\n\n"
                "### 📱 お支払い方法\n"
                "・⭐ **PayPay 送金リンク【おすすめ！】**（PayPayアプリでリンクを作成）\n"
                "・**Amazon ギフトカード番号**\n"
                "※保護者の同意・クレジットカード不要でご利用いただけます。"
            ),
            color=0xFFD700
        )
        view = ProGuidanceView(self.bot)

        await interaction.response.defer(ephemeral=True)
        # DMで送信を試みる
        dm_sent = False
        try:
            dm_channel = interaction.user.dm_channel or await interaction.user.create_dm()
            await dm_channel.send(embed=embed, view=view)
            dm_sent = True
        except Exception:
            dm_sent = False

        if dm_sent:
            await interaction.followup.send(
                "💌 **DMにPro & Pro Maxプランのご案内を送信しました！**\n（DMを開いてご確認くださいね♡）",
                ephemeral=True
            )
        else:
            # DMが閉じられている場合はエフェメラルで直接表示
            await interaction.followup.send(
                "⚠️ DMへの送信がブロックされています。こちらで直接表示しますね！",
                embed=embed,
                view=view,
                ephemeral=True
            )

    @app_commands.command(name="pro_pay", description="PayPay送金リンクまたはAmazonギフトコードを提出してPro/Pro Maxプランを申請します")
    @app_commands.describe(content="PayPay送金リンク(https://...) または Amazonギフトコード")
    async def pro_pay_cmd(self, interaction: discord.Interaction, content: str):
        await interaction.response.defer(ephemeral=True)
        if hasattr(self.bot, 'is_campaign_active') and self.bot.is_campaign_active():
            return await interaction.followup.send(
                "🎉 **【10/4〜10/11 期間限定】全機能無料開放キャンペーン中！**\n"
                "現在、すべてのユーザー様に **Pro MAXと同等の全機能** を無料で開放しております！\n"
                "キャンペーン期間中は有料機能の課金受付を停止しておりますので、このまま無料で全機能をお楽しみください♡\n"
                "（※利用量によっては全体に制限をかける可能性があります。期間は変更される可能性があります）",
                ephemeral=True
            )
        content = content.strip()
        user_id = str(interaction.user.id)
        now_str = datetime.now(timezone(timedelta(hours=9))).isoformat()

        req_id = None
        with contextlib.closing(sqlite3.connect("database.db", timeout=30.0)) as conn, conn:
            c = conn.cursor()
            c.execute(
                "INSERT INTO gift_requests (user_id, pay_content, status, created_at) VALUES (?, ?, 'pending', ?)",
                (user_id, content, now_str)
            )
            req_id = c.lastrowid
            conn.commit()

        cancel_view = UserCancelRequestView(self.bot, req_id)
        embed = discord.Embed(
            title="⏳ 支払い申請を受け付けました！",
            description=(
                f"ご主人様、プランのお申し込みありがとうございます♡\n"
                f"作者が内容を確認次第、プランが自動で有効化されます。\n\n"
                f"**提出内容**: `{content}`\n"
                f"**申請ID**: `#{req_id}`\n\n"
                f"※確認完了まで今しばらくお待ちください。"
            ),
            color=0xffb6c1
        )
        await interaction.followup.send(embed=embed, view=cancel_view, ephemeral=True)

        # 管理者へ通知
        modal_helper = PaymentModal(self.bot)
        await modal_helper._notify_admin(interaction.user, content, req_id)

    @app_commands.command(name="plan", description="現在のプランと本日のAI会話残り回数を確認します")
    async def plan_cmd(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        user_id = str(interaction.user.id)
        user_plan = self.bot.get_user_plan(user_id)
        is_owner = self.bot.is_owner(user_id)
        
        plan_type_str = "無料プラン (Free)"
        expires_str = "なし"
        max_daily = 100
        daily_used = 0

        now_date = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d")

        with contextlib.closing(sqlite3.connect("database.db", timeout=30.0)) as conn, conn:
            c = conn.cursor()
            row = c.execute("SELECT plan_type, expires_at, daily_ai_count, last_reset_date FROM user_subscriptions WHERE user_id = ?", (user_id,)).fetchone()
            if row:
                p_type, exp, used, l_date = row
                if l_date == now_date:
                    daily_used = used
                if exp:
                    expires_str = exp[:10]

        is_campaign = hasattr(self.bot, 'is_campaign_active') and self.bot.is_campaign_active()

        if is_owner:
            plan_type_str = "👑 開発者・完全無制限オーナー"
            expires_str = "無期限 (永続)"
            max_daily = 99999
            color = 0xFF4500
        elif is_campaign:
            plan_type_str = "🎉 期間限定: 全員Pro MAX無料開放中！"
            expires_str = "2026-10-11まで (無料開放)"
            max_daily = 1000
            color = 0xE5E4E2
        elif user_plan == 'promax_lifetime':
            plan_type_str = "👑 買い切りPro Max (永続・最上級貴族)"
            expires_str = "無期限 (永続)"
            max_daily = 1000
            color = 0xE5E4E2
        elif user_plan == 'promax_monthly':
            plan_type_str = "👑 月額Pro Max (最上級貴族)"
            max_daily = 1000
            color = 0xE5E4E2
        elif user_plan == 'pro_lifetime':
            plan_type_str = "💎 買い切りPro (永続)"
            expires_str = "無期限 (永続)"
            max_daily = 300
            color = 0xFFD700
        elif user_plan == 'pro_monthly':
            plan_type_str = "💎 月額Pro"
            max_daily = 300
            color = 0xFFD700
        else:
            plan_type_str = "無料プラン (Free)"
            expires_str = "なし"
            max_daily = 100
            color = 0x87ceeb

        remain_str = "無制限" if is_owner else f"{max(0, max_daily - daily_used)} 回"
        used_str = f"{daily_used} 回" if is_owner else f"{daily_used} / {max_daily} 回"

        embed = discord.Embed(
            title="📊 あなたの現在のプラン状況",
            color=color
        )
        embed.add_field(name="現在のプラン", value=f"**{plan_type_str}**", inline=True)
        embed.add_field(name="有効期限", value=f"`{expires_str}`", inline=True)
        embed.add_field(
            name="本日のAI会話回数",
            value=f"**{used_str}** (残り: **{remain_str}**)",
            inline=False
        )
        if is_campaign:
            embed.set_footer(text="🎉 10/4~10/11は全機能無料開放期間中！Pro MAXのすべての機能をお楽しみいただけます♡")
        elif user_plan == 'free':
            embed.set_footer(text="💡 `/pro` でPro / Pro Maxプランの特典や詳細を確認できます♡")
        else:
            embed.set_footer(text="✨ いつもまきぐもを応援してくれてありがとうございます♡")

        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="grant_pro", description="【管理者限定】指定したユーザーにPro / Pro Maxプランを手動で付与します")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(user="付与対象のユーザー", plan_type="プランの種類", days="有効日数 (買い切りは9999)")
    @app_commands.choices(plan_type=[
        app_commands.Choice(name="✨ 月額Pro (100円/30日)", value="pro_monthly"),
        app_commands.Choice(name="💎 買い切りPro (500円/永続)", value="pro_lifetime"),
        app_commands.Choice(name="🔥 月額Pro Max (250円/30日)", value="promax_monthly"),
        app_commands.Choice(name="👑 買い切りPro Max (1500円/永続)", value="promax_lifetime"),
        app_commands.Choice(name="❌ 無料プランに戻す (free)", value="free"),
    ])
    async def grant_pro_cmd(self, interaction: discord.Interaction, user: discord.User, plan_type: app_commands.Choice[str], days: int = 30):
        await interaction.response.defer(ephemeral=True)
        admin_id = os.getenv('ADMIN_USER_ID')
        
        # ADMIN_USER_ID で指定されたユーザーのみ実行可能
        if not admin_id or str(interaction.user.id) != str(admin_id):
            return await interaction.followup.send("❌ このコマンドはBot管理者(ADMIN_USER_ID)のみ実行できます。", ephemeral=True)

        target_uid = str(user.id)
        now = datetime.now(timezone(timedelta(hours=9)))
        if 'lifetime' in plan_type.value or days >= 9000:
            expires_at = '9999-12-31T23:59:59'
        elif plan_type.value == 'free':
            expires_at = None
        else:
            expires_at = (now + timedelta(days=days)).isoformat()

        with contextlib.closing(sqlite3.connect("database.db", timeout=30.0)) as conn, conn:
            c = conn.cursor()
            c.execute(
                "INSERT INTO user_subscriptions (user_id, plan_type, expires_at, reminded_3days) VALUES (?, ?, ?, 0) "
                "ON CONFLICT(user_id) DO UPDATE SET plan_type = ?, expires_at = ?, reminded_3days = 0",
                (target_uid, plan_type.value, expires_at, plan_type.value, expires_at)
            )
            conn.commit()

        await interaction.followup.send(
            f"✅ {user.mention} (`{user.display_name}`) に **{plan_type.name}** を設定しました。（期限: `{expires_at}`）",
            ephemeral=True
        )

    @tasks.loop(hours=1)
    async def check_subscriptions(self):
        if not self.bot.is_ready():
            return

        now = datetime.now(timezone(timedelta(hours=9)))

        try:
            with contextlib.closing(sqlite3.connect("database.db", timeout=30.0)) as conn, conn:
                c = conn.cursor()
                rows = c.execute("SELECT user_id, plan_type, expires_at, reminded_3days FROM user_subscriptions WHERE plan_type IN ('pro_monthly', 'promax_monthly')").fetchall()
                
                for uid, p_type, exp_str, reminded in rows:
                    if not exp_str:
                        continue
                    try:
                        exp_dt = datetime.fromisoformat(exp_str)
                        if exp_dt.tzinfo is None:
                            exp_dt = exp_dt.replace(tzinfo=timezone(timedelta(hours=9)))
                        
                        delta = exp_dt - now
                        # 期限切れ
                        if delta.total_seconds() <= 0:
                            c.execute("UPDATE user_subscriptions SET plan_type = 'free' WHERE user_id = ?", (uid,))
                            try:
                                user = await self.bot.fetch_user(int(uid))
                                if user:
                                    await user.send(f"「本日で有料プラン({p_type})の有効期限が終了しました。引き続き特別扱いされたいなら `/pro` からいつでも更新してくださいね……？」")
                            except Exception:
                                pass
                        # 3日前リマインド (残り72時間以下かつ未送信)
                        elif delta.total_seconds() <= 72 * 3600 and reminded == 0:
                            c.execute("UPDATE user_subscriptions SET reminded_3days = 1 WHERE user_id = ?", (uid,))
                            try:
                                user = await self.bot.fetch_user(int(uid))
                                if user:
                                    days_left = max(1, int(delta.total_seconds() // 86400))
                                    await user.send(f"「……あのね、あと **{days_left}日** であなたの有料プランが切れちゃいます。\n別に……更新してくれなくても困りませんけど、また冷たくされても知りませんからね？♡\n（`/pro` で更新できます）」")
                            except Exception:
                                pass
                    except Exception:
                        pass
                conn.commit()
        except Exception as e:
            print(f"Subscription monitor error: {e}")

    @check_subscriptions.before_loop
    async def before_check_subscriptions(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(Billing(bot))
