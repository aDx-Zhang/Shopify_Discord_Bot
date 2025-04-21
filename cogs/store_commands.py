
import discord
from discord import app_commands
from discord.ext import commands

class StoreCommands(commands.Cog):
    @app_commands.command(name="add_store", description="Add a Shopify store to monitor")
    async def add_store(self, interaction: discord.Interaction, store_url: str):
        user_id = str(interaction.user.id)
        user_data = load_user_data(user_id)
        
        if "stores" not in user_data:
            user_data["stores"] = []
            
        user_data["stores"].append(store_url)
        save_user_data(user_id, user_data)
        
        await interaction.response.send_message(f"Store {store_url} added successfully", ephemeral=True)

async def setup(bot):
    await bot.add_cog(StoreCommands(bot))
