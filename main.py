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
    view = ChannelSelectView(message)
    await interaction.response.send_message("Select destination:", view=view, ephemeral=True)

class ChannelSelectView(discord.ui.View):
    def __init__(self, msg):
        super().__init__()
        self.msg = msg

    @discord.ui.select(cls=discord.ui.ChannelSelect, 
                       channel_types=[discord.ChannelType.text, discord.ChannelType.public_thread, discord.ChannelType.private_thread, discord.ChannelType.forum])
    async def select_channel(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Fetch the full channel object
            selected_id = select.values[0].id
            target_channel = await self.msg.guild.fetch_channel(selected_id)
            
            # Prepare files
            files = []
            for attachment in self.msg.attachments:
                files.append(await attachment.to_file())

            # Determine if target is a thread or standard channel
            if isinstance(target_channel, discord.Thread):
                webhook_channel = target_channel.parent
                thread_to_use = target_channel
            else:
                webhook_channel = target_channel
                thread_to_use = discord.utils.MISSING

            # Webhook Setup
            webhooks = await webhook_channel.webhooks()
            webhook = discord.utils.get(webhooks, name="Movr Helper")
            if not webhook:
                webhook = await webhook_channel.create_webhook(name="Movr Helper")

            # Send the message
            sent_msg = await webhook.send(
                content=self.msg.content,
                username=self.msg.author.display_name,
                avatar_url=self.msg.author.display_avatar.url,
                files=files,
                thread=thread_to_use,
                wait=True
            )

            # Carry over reactions
            for reaction in self.msg.reactions:
                try:
                    await sent_msg.add_reaction(reaction.emoji)
                except:
                    continue 

            await asyncio.sleep(0.5) 
            await self.msg.delete()
            await interaction.followup.send(f"Successfully moved!", ephemeral=True)
            
        except Exception as e:
            print(f"❌ ERROR: {e}")
            await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)

bot.run(TOKEN)