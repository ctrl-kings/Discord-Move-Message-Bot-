import discord
import os
import asyncio
from dotenv import load_dotenv 
from discord import app_commands
from discord.ext import commands
from typing import List

load_dotenv()
TOKEN = os.getenv('BOT_TOKEN') 

class MoveBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        self.tree.add_command(move_messages_context)
        await self.tree.sync()
        print("Ctrl Kings: Movr Bot is online and ready!")

bot = MoveBot()

# --- THE MODAL FOR CUSTOM INPUT ---
class CustomAmountModal(discord.ui.Modal, title='Move Custom Amount'):
    amount = discord.ui.TextInput(
        label='How many messages?',
        placeholder='Enter a number (1-100)...',
        min_length=1,
        max_length=3,
    )

    def __init__(self, target_msg, target_channel, parent_view):
        super().__init__()
        self.target_msg = target_msg
        self.target_channel = target_channel
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            count = int(self.amount.value)
            if count < 1 or count > 100:
                return await interaction.response.send_message("Please enter a number between 1 and 100.", ephemeral=True)
            await self.parent_view.perform_move(interaction, count)
        except ValueError:
            await interaction.response.send_message("That's not a valid number!", ephemeral=True)

# --- THE CONTEXT MENU COMMAND ---
@app_commands.context_menu(name="Move Messages")
@app_commands.default_permissions(manage_messages=True)
async def move_messages_context(interaction: discord.Interaction, message: discord.Message):
    view = ChannelSelectView(message)
    await interaction.response.send_message("1️⃣ **Select destination channel:**", view=view, ephemeral=True)

# --- STEP 1: CHANNEL SELECTION & PERMISSION CHECK ---
class ChannelSelectView(discord.ui.View):
    def __init__(self, msg):
        super().__init__(timeout=180)
        self.msg = msg

    @discord.ui.select(cls=discord.ui.ChannelSelect, 
                        channel_types=[discord.ChannelType.text, discord.ChannelType.public_thread, discord.ChannelType.private_thread])
    async def select_channel(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        selected_id = select.values[0].id
        target_channel = await self.msg.guild.fetch_channel(selected_id)
        
        # QOL: Permission Auto-Check
        perms = target_channel.permissions_for(self.msg.guild.me)
        if not perms.manage_webhooks or not perms.send_messages:
            return await interaction.response.send_message(f"❌ **Permission Error:** I need `Manage Webhooks` and `Send Messages` in {target_channel.mention}!", ephemeral=True)

        count_view = MessageCountView(self.msg, target_channel)
        await interaction.response.edit_message(
            content=f"2️⃣ **Target:** {target_channel.mention}\nHow many messages should I move?", 
            view=count_view
        )

# --- STEP 2: QUANTITY & PROGRESS ---
class MessageCountView(discord.ui.View):
    def __init__(self, target_msg, target_channel):
        super().__init__(timeout=180)
        self.target_msg = target_msg
        self.target_channel = target_channel

    async def perform_move(self, interaction: discord.Interaction, count: int):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        
        try:
            messages_to_move = []
            if count > 1:
                async for m in self.target_msg.channel.history(limit=count-1, before=self.target_msg):
                    messages_to_move.append(m)
            messages_to_move.reverse() 
            messages_to_move.append(self.target_msg)

            dest = self.target_channel
            webhook_channel = dest.parent if isinstance(dest, discord.Thread) else dest
            thread_to_use = dest if isinstance(dest, discord.Thread) else discord.utils.MISSING
            
            webhooks = await webhook_channel.webhooks()
            webhook = discord.utils.get(webhooks, name="Movr Helper") or await webhook_channel.create_webhook(name="Movr Helper")

            total = len(messages_to_move)
            
            # QOL: Live Progress Embed
            for i, m in enumerate(messages_to_move, 1):
                progress_bar = "■" * i + "□" * (total - i)
                await interaction.edit_original_response(content=f"📦 **Moving Messages...**\n`{progress_bar}` ({i}/{total})", view=None)

                files = []
                for attachment in m.attachments:
                    files.append(await attachment.to_file())
                
                sent_msg = await webhook.send(
                    content=m.content,
                    username=m.author.display_name,
                    avatar_url=m.author.display_avatar.url,
                    files=files,
                    thread=thread_to_use,
                    wait=True
                )

                for r in m.reactions:
                    try: await sent_msg.add_reaction(r.emoji)
                    except: continue

                await m.delete()
                await asyncio.sleep(0.5) # Slight delay for embed stability

            await interaction.edit_original_response(content=f"✅ **Move Complete!** Moved {total} messages to {dest.mention}.", view=None)
            
        except Exception as e:
            print(f"❌ ERROR: {e}")
            await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)

    @discord.ui.button(label="Just this 1", style=discord.ButtonStyle.gray)
    async def one(self, interaction, button): await self.perform_move(interaction, 1)

    @discord.ui.button(label="Last 5", style=discord.ButtonStyle.primary)
    async def five(self, interaction, button): await self.perform_move(interaction, 5)

    @discord.ui.button(label="Last 10", style=discord.ButtonStyle.danger)
    async def ten(self, interaction, button): await self.perform_move(interaction, 10)

    @discord.ui.button(label="Custom Amount", style=discord.ButtonStyle.success)
    async def custom(self, interaction, button):
        await interaction.response.send_modal(CustomAmountModal(self.target_msg, self.target_channel, self))

bot.run(TOKEN)