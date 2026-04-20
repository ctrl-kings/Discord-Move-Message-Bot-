import discord
import os
import asyncio
from dotenv import load_dotenv 
from discord import app_commands
from discord.ext import commands

load_dotenv()
TOKEN = os.getenv('BOT_TOKEN') 
# Pulls your ID from the environment for security
OWNER_ID = int(os.getenv('OWNER_ID') or 1187154363622367285)

class MoveBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.guilds = True  # Required for broadcast to find servers
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        self.tree.add_command(move_messages_context)
        self.tree.add_command(broadcast) # Registers the new broadcast command
        await self.tree.sync()
        print(f"Ctrl Kings: Movr Bot is online. Owner ID {OWNER_ID} recognized.")

bot = MoveBot()

# --- THE BROADCAST COMMAND (Owner Only) ---
@app_commands.command(name="broadcast", description="Sends an update DM to all server owners")
async def broadcast(interaction: discord.Interaction, message: str):
    if interaction.user.id != OWNER_ID:
        return await interaction.response.send_message("Access Denied: Owner Only Command.", ephemeral=True)

    await interaction.response.send_message(f"Initiating broadcast...", ephemeral=True)
    
    success, fail = 0, 0
    for guild in bot.guilds:
        try:
            if guild.owner:
                embed = discord.Embed(
                    title="Movr Update",
                    description=message,
                    color=discord.Color.blue()
                )
                embed.set_footer(text=f"Sent to: {guild.name}")
                await guild.owner.send(embed=embed)
                success += 1
                await asyncio.sleep(1.5) # Anti-spam delay
        except:
            fail += 1

    await interaction.followup.send(f"Broadcast Complete. Success: {success} | Failed: {fail}")

# --- REVERSE VIEW (30-Second Window) ---
class ReverseView(discord.ui.View):
    def __init__(self, data, current_channel):
        super().__init__(timeout=30)
        self.data = data
        self.current_channel = current_channel

    @discord.ui.button(label="Reverse Move (30s)", style=discord.ButtonStyle.secondary)
    async def reverse_action(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        button.disabled = True
        await interaction.edit_original_response(view=self)

        total = len(self.data)
        first_item = self.data[0]
        orig_channel = first_item["original_channel"]
        
        webhook_channel = orig_channel.parent if isinstance(orig_channel, discord.Thread) else orig_channel
        webhooks = await webhook_channel.webhooks()
        webhook = discord.utils.get(webhooks, name="Movr Helper") or await webhook_channel.create_webhook(name="Movr Helper")

        for i, item in enumerate(self.data, 1):
            progress = "■" * i + "□" * (total - i)
            await interaction.edit_original_response(content=f"Reversing Move\n{progress} ({i}/{total})")

            await webhook.send(
                content=item["content"],
                username=item["author_name"],
                avatar_url=item["author_avatar"],
                wait=True
            )

            try:
                msg_to_del = await self.current_channel.fetch_message(item["new_msg_id"])
                await msg_to_del.delete()
            except: pass
            
            await asyncio.sleep(0.4)
        await interaction.edit_original_response(content="Reverse Complete.", view=None)

# --- MODAL FOR CUSTOM INPUT ---
class CustomAmountModal(discord.ui.Modal, title='Move Custom Amount'):
    amount = discord.ui.TextInput(label='How many messages?', placeholder='1-100...', min_length=1, max_length=3)

    def __init__(self, target_msg, target_channel, parent_view):
        super().__init__()
        self.target_msg, self.target_channel, self.parent_view = target_msg, target_channel, parent_view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            count = int(self.amount.value)
            if 1 <= count <= 100:
                await self.parent_view.perform_move(interaction, count)
            else:
                await interaction.response.send_message("Enter 1-100.", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("Invalid number.", ephemeral=True)

# --- CONTEXT MENU & VIEWS ---
@app_commands.context_menu(name="Move Messages")
@app_commands.default_permissions(manage_messages=True)
async def move_messages_context(interaction: discord.Interaction, message: discord.Message):
    view = ChannelSelectView(message)
    await interaction.response.send_message("1. Select destination channel:", view=view, ephemeral=True)

class ChannelSelectView(discord.ui.View):
    def __init__(self, msg):
        super().__init__(timeout=180)
        self.msg = msg

    @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.text, discord.ChannelType.public_thread, discord.ChannelType.private_thread])
    async def select_channel(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        target_channel = await self.msg.guild.fetch_channel(select.values[0].id)
        perms = target_channel.permissions_for(self.msg.guild.me)
        if not perms.manage_webhooks or not perms.send_messages:
            return await interaction.response.send_message(f"Error: Permissions missing in {target_channel.mention}", ephemeral=True)

        await interaction.response.edit_message(content=f"2. Target: {target_channel.mention}", view=MessageCountView(self.msg, target_channel))

class MessageCountView(discord.ui.View):
    def __init__(self, target_msg, target_channel):
        super().__init__(timeout=180)
        self.target_msg, self.target_channel = target_msg, target_channel

    async def perform_move(self, interaction: discord.Interaction, count: int):
        if not interaction.response.is_done(): await interaction.response.defer(ephemeral=True)
        for item in self.children: item.disabled = True
        await interaction.edit_original_response(view=self)

        try:
            messages_to_move = []
            async for m in self.target_msg.channel.history(limit=count, before=self.target_msg.created_at, oldest_first=False):
                messages_to_move.append(m)
            # Ensure we include the selected message
            if self.target_msg not in messages_to_move: messages_to_move.insert(0, self.target_msg)
            messages_to_move = messages_to_move[:count]
            messages_to_move.reverse()

            dest = self.target_channel
            webhook_channel = dest.parent if isinstance(dest, discord.Thread) else dest
            webhooks = await webhook_channel.webhooks()
            webhook = discord.utils.get(webhooks, name="Movr Helper") or await webhook_channel.create_webhook(name="Movr Helper")

            moved_data = []
            for i, m in enumerate(messages_to_move, 1):
                await interaction.edit_original_response(content=f"Moving Messages\n{'■' * i + '□' * (len(messages_to_move) - i)} ({i}/{len(messages_to_move)})")
                
                files = [await a.to_file() for a in m.attachments]
                sent_msg = await webhook.send(
                    content=m.content, username=m.author.display_name, avatar_url=m.author.display_avatar.url,
                    files=files, thread=dest if isinstance(dest, discord.Thread) else discord.utils.MISSING, wait=True
                )
                moved_data.append({"content": m.content, "author_name": m.author.display_name, "author_avatar": m.author.display_avatar.url, "new_msg_id": sent_msg.id, "original_channel": m.channel})
                await m.delete()
                await asyncio.sleep(0.4)

            await interaction.edit_original_response(content=f"Move Complete.", view=ReverseView(moved_data, dest))
        except Exception as e:
            print(f"Error: {e}")

    @discord.ui.button(label="1", style=discord.ButtonStyle.gray)
    async def one(self, interaction, button): await self.perform_move(interaction, 1)
    @discord.ui.button(label="5", style=discord.ButtonStyle.primary)
    async def five(self, interaction, button): await self.perform_move(interaction, 5)
    @discord.ui.button(label="10", style=discord.ButtonStyle.danger)
    async def ten(self, interaction, button): await self.perform_move(interaction, 10)
    @discord.ui.button(label="Custom", style=discord.ButtonStyle.success)
    async def custom(self, interaction, button): await interaction.response.send_modal(CustomAmountModal(self.target_msg, self.target_channel, self))

bot.run(TOKEN)