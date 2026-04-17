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
        # Updated to reflect your new brand
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

    @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.text])
    async def select_channel(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        await interaction.response.defer(ephemeral=True)
        
        target_id = select.values[0].id
        
        target_channel = await self.msg.guild.fetch_channel(target_id)
        
        # Move attachments
        files = []
        for attachment in self.msg.attachments:
            files.append(await attachment.to_file())

        # Professional header format
        header = f"**[Moved from {self.msg.channel.mention} by Ctrl Kings]**\n**{self.msg.author.display_name}:** "
        
        try:
            await target_channel.send(content=f"{header}{self.msg.content}", files=files)
            
            # Tiny delay to ensure Discord registers the send before the delete
            await asyncio.sleep(0.5) 
            
            await self.msg.delete()
            await interaction.followup.send("Successfully moved and deleted original!", ephemeral=True)
            print(f"✅ Success: Moved message from {self.msg.author}")
            
        except discord.Forbidden:
            print(f"❌ PERMISSION ERROR: Bot cannot delete message from {self.msg.author}. Check Role Hierarchy.")
            await interaction.followup.send("Moved, but Discord blocked the delete. Check Role Hierarchy!", ephemeral=True)
        except Exception as e:
            print(f"❌ ERROR: {e}")
            await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)

bot.run(TOKEN)