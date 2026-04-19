import discord
import os
import asyncio
from dotenv import load_dotenv 
from discord import app_commands
from discord.ext import commands

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

# --- THE CONTEXT MENU COMMAND ---
@app_commands.context_menu(name="Move Messages")
@app_commands.default_permissions(manage_messages=True)
async def move_messages_context(interaction: discord.Interaction, message: discord.Message):
    view = ChannelSelectView(message)
    await interaction.response.send_message("1️⃣ **Select destination channel:**", view=view, ephemeral=True)

# --- STEP 1: CHANNEL SELECTION ---
class ChannelSelectView(discord.ui.View):
    def __init__(self, msg):
        super().__init__(timeout=180)
        self.msg = msg

    @discord.ui.select(cls=discord.ui.ChannelSelect, 
                        channel_types=[discord.ChannelType.text, discord.ChannelType.public_thread, discord.ChannelType.private_thread, discord.ChannelType.forum])
    async def select_channel(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        try:
            selected_id = select.values[0].id
            target_channel = await self.msg.guild.fetch_channel(selected_id)
            
            # Switch to the count selection view (your bulk logic)
            count_view = MessageCountView(self.msg, target_channel)
            await interaction.response.edit_message(
                content=f"2️⃣ **Target:** {target_channel.mention}\nHow many messages (including the one clicked) should I move?", 
                view=count_view
            )
        except Exception as e:
            await interaction.followup.send(f"❌ Error fetching channel: {e}", ephemeral=True)

# --- STEP 2: QUANTITY SELECTION & EXECUTION ---
class MessageCountView(discord.ui.View):
    def __init__(self, target_msg, target_channel):
        super().__init__(timeout=180)
        self.target_msg = target_msg
        self.target_channel = target_channel

    async def perform_move(self, interaction: discord.Interaction, count: int):
        await interaction.response.defer(ephemeral=True)
        
        try:
            messages_to_move = []
            
            # 1. Fetch History (Chronological)
            if count > 1:
                async for m in self.target_msg.channel.history(limit=count-1, before=self.target_msg):
                    messages_to_move.append(m)
            
            messages_to_move.reverse() # Sort from oldest to newest
            messages_to_move.append(self.target_msg) # Add the right-clicked message last

            # 2. Webhook Setup
            dest = self.target_channel
            webhook_channel = dest.parent if isinstance(dest, discord.Thread) else dest
            thread_to_use = dest if isinstance(dest, discord.Thread) else discord.utils.MISSING
            
            webhooks = await webhook_channel.webhooks()
            webhook = discord.utils.get(webhooks, name="Movr Helper") or await webhook_channel.create_webhook(name="Movr Helper")

            # 3. Execution Loop
            for m in messages_to_move:
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

                # Carry over reactions (keeping this logic from the merge)
                for reaction in m.reactions:
                    try:
                        await sent_msg.add_reaction(reaction.emoji)
                    except:
                        continue

                await m.delete()
                await asyncio.sleep(0.4) # Protect against rate limits

            await interaction.followup.send(f"✅ Successfully moved {len(messages_to_move)} messages!", ephemeral=True)
            
        except Exception as e:
            print(f"❌ ERROR: {e}")
            await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)

    @discord.ui.button(label="Just this 1", style=discord.ButtonStyle.gray)
    async def one(self, interaction, button):
        await self.perform_move(interaction, 1)

    @discord.ui.button(label="Last 5", style=discord.ButtonStyle.primary)
    async def five(self, interaction, button):
        await self.perform_move(interaction, 5)

    @discord.ui.button(label="Last 10", style=discord.ButtonStyle.danger)
    async def ten(self, interaction, button):
        await self.perform_move(interaction, 10)

bot.run(TOKEN)