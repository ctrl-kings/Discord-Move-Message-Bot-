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
        self.tree.add_command(move_message)
        await self.tree.sync()
        print("Ctrl Kings: Movr Bot is online and ready!")

bot = MoveBot()

@app_commands.context_menu(name="Move Message")
@app_commands.default_permissions(manage_messages=True)
async def move_message(interaction: discord.Interaction, message: discord.Message):
    # Added support for Forum/Thread detection in the view
    view = ChannelSelectView(message)
    await interaction.response.send_message("Select destination:", view=view, ephemeral=True)

class ChannelSelectView(discord.ui.View):
    def __init__(self, msg):
        super().__init__()
        self.msg = msg

    # Updated to allow selecting Text Channels, Threads, and Forum Channels
    @discord.ui.select(cls=discord.ui.ChannelSelect, 
                       channel_types=[discord.ChannelType.text, discord.ChannelType.public_thread, discord.ChannelType.private_thread, discord.ChannelType.forum])
    async def select_channel(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        await interaction.response.defer(ephemeral=True)
        
        target_channel = select.values[0]
        
        # 1. HANDLE ATTACHMENTS
        files = []
        for attachment in self.msg.attachments:
            files.append(await attachment.to_file())

        try:
            # 2. WEBHOOK LOGIC (PRESERVE ORIGINALITY)
            # If the target is a thread, we need the parent channel to find/create a webhook
            if isinstance(target_channel, discord.Thread):
                webhook_channel = target_channel.parent
                thread_id = target_channel.id
            else:
                webhook_channel = target_channel
                thread_id = None

            # Find an existing Movr webhook or create a new one
            webhooks = await webhook_channel.webhooks()
            webhook = discord.utils.get(webhooks, name="Movr Helper")
            if not webhook:
                webhook = await webhook_channel.create_webhook(name="Movr Helper")

            # 3. SEND VIA WEBHOOK (Impersonates the user)
            sent_msg = await webhook.send(
                content=self.msg.content,
                username=self.msg.author.display_name,
                avatar_url=self.msg.author.display_avatar.url,
                files=files,
                thread=target_channel if thread_id else discord.utils.MISSING, # Thread support
                wait=True
            )

            # 4. EMOJI REACTION CARRY-OVER
            for reaction in self.msg.reactions:
                try:
                    # We can only easily carry over standard emojis or ones the bot has access to
                    await sent_msg.add_reaction(reaction.emoji)
                except:
                    continue # Skip if bot doesn't have access to a specific custom emoji

            # 5. CLEANUP
            await asyncio.sleep(0.5) 
            await self.msg.delete()
            await interaction.followup.send(f"Successfully moved to {target_channel.mention}!", ephemeral=True)
            print(f"✅ Success: Moved message from {self.msg.author} using Webhook")
            
        except discord.Forbidden:
            print(f"❌ PERMISSION ERROR: Check Webhook/Delete permissions.")
            await interaction.followup.send("Error: I need 'Manage Webhooks' and 'Manage Messages' permissions!", ephemeral=True)
        except Exception as e:
            print(f"❌ ERROR: {e}")
            await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)

bot.run(TOKEN)