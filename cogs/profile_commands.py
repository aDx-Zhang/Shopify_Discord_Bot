import discord
from discord import app_commands
from discord.ext import commands
import logging
import json
import asyncio
from typing import Dict, List, Optional
from utils.database import save_user_data, load_user_data

logger = logging.getLogger(__name__)

class ProfileCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Cache to store user info during profile creation
        self.profile_creation_cache = {}
    
    @app_commands.command(name="start", description="Start using the Shopify bot")
    async def start(self, interaction: discord.Interaction):
        """Command to start using the bot."""
        user_id = str(interaction.user.id)
        
        # Load existing user data or create new
        user_data = load_user_data(user_id)
        if not user_data:
            user_data = {
                "profiles": [],
                "monitoring_tasks": [],
                "checkout_tasks": []
            }
            save_user_data(user_id, user_data)
        
        embed = discord.Embed(
            title="Welcome to Shopify Bot",
            description="Thanks for using the Shopify Bot! Here are the available commands:",
            color=discord.Color.blue()
        )
        
        embed.add_field(name="/profile", value="Create a checkout profile", inline=False)
        embed.add_field(name="/monitor", value="Monitor a Shopify product", inline=False)
        embed.add_field(name="/add_task", value="Add a checkout task", inline=False)
        embed.add_field(name="/list_profiles", value="List your saved profiles", inline=False)
        embed.add_field(name="/list_tasks", value="List your active tasks", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="profile", description="Create a new checkout profile")
    async def profile(self, interaction: discord.Interaction, profile_name: str):
        """Command to create a new checkout profile."""
        user_id = str(interaction.user.id)
        
        # Initialize the profile creation process
        self.profile_creation_cache[user_id] = {
            "step": 1,
            "profile_name": profile_name,
            "data": {}
        }
        
        embed = discord.Embed(
            title="Profile Creation",
            description=f"Creating profile: {profile_name}",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="Step 1 of 9: Email",
            value="Please enter your email address",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """Listen for messages for the profile creation workflow."""
        # Ignore messages from bots or in non-DM channels
        if message.author.bot or not isinstance(message.channel, discord.DMChannel):
            return
        
        user_id = str(message.author.id)
        if user_id not in self.profile_creation_cache:
            return
        
        profile_cache = self.profile_creation_cache[user_id]
        step = profile_cache["step"]
        content = message.content.strip()
        
        # Handle profile creation steps
        if step == 1:  # Email
            profile_cache["data"]["email"] = content
            await self._prompt_next_step(message, user_id, "First Name", "Enter your first name")
        
        elif step == 2:  # First Name
            profile_cache["data"]["first_name"] = content
            await self._prompt_next_step(message, user_id, "Last Name", "Enter your last name")
        
        elif step == 3:  # Last Name
            profile_cache["data"]["last_name"] = content
            await self._prompt_next_step(message, user_id, "Address Line 1", "Enter your address (line 1)")
        
        elif step == 4:  # Address Line 1
            profile_cache["data"]["address1"] = content
            await self._prompt_next_step(message, user_id, "Address Line 2 (Optional)", "Enter address line 2 (or type 'skip' to skip)")
        
        elif step == 5:  # Address Line 2
            if content.lower() != "skip":
                profile_cache["data"]["address2"] = content
            await self._prompt_next_step(message, user_id, "City", "Enter your city")
        
        elif step == 6:  # City
            profile_cache["data"]["city"] = content
            await self._prompt_next_step(message, user_id, "Postal/ZIP Code", "Enter your postal/ZIP code")
        
        elif step == 7:  # Postal Code
            profile_cache["data"]["zip"] = content
            await self._prompt_next_step(message, user_id, "Phone Number", "Enter your phone number")
        
        elif step == 8:  # Phone
            profile_cache["data"]["phone"] = content
            await self._prompt_next_step(message, user_id, "Payment Information", 
                                        "Enter your card details in this format: CARDNUMBER|MM|YYYY|CVV")
        
        elif step == 9:  # Card Details
            try:
                card_parts = content.split('|')
                if len(card_parts) != 4:
                    await message.channel.send("Invalid card format. Please use: CARDNUMBER|MM|YYYY|CVV")
                    return
                    
                profile_cache["data"]["card_number"] = card_parts[0]
                profile_cache["data"]["card_month"] = card_parts[1]
                profile_cache["data"]["card_year"] = card_parts[2]
                profile_cache["data"]["card_cvv"] = card_parts[3]
                
                # Save the completed profile
                await self._save_profile(message, user_id)
            except Exception as e:
                logger.error(f"Error processing card details: {e}")
                await message.channel.send("There was an error processing your card details. Please try again.")
    
    async def _prompt_next_step(self, message, user_id, step_name, prompt):
        """Helper method to prompt for the next profile creation step."""
        profile_cache = self.profile_creation_cache[user_id]
        profile_cache["step"] += 1
        
        embed = discord.Embed(
            title=f"Profile Creation: {profile_cache['profile_name']}",
            description=f"Step {profile_cache['step']} of 9: {step_name}",
            color=discord.Color.green()
        )
        embed.add_field(name="Instructions", value=prompt, inline=False)
        
        await message.channel.send(embed=embed)
    
    async def _save_profile(self, message, user_id):
        """Save the completed profile to the user's data."""
        profile_cache = self.profile_creation_cache[user_id]
        
        # Load user data
        user_data = load_user_data(user_id)
        if not user_data:
            user_data = {"profiles": [], "monitoring_tasks": [], "checkout_tasks": []}
        
        # Create the profile object
        new_profile = {
            "name": profile_cache["profile_name"],
            **profile_cache["data"]
        }
        
        # Add or update the profile
        profile_exists = False
        for i, profile in enumerate(user_data["profiles"]):
            if profile["name"] == new_profile["name"]:
                user_data["profiles"][i] = new_profile
                profile_exists = True
                break
        
        if not profile_exists:
            user_data["profiles"].append(new_profile)
        
        # Save updated user data
        save_user_data(user_id, user_data)
        
        # Clean up the cache
        del self.profile_creation_cache[user_id]
        
        embed = discord.Embed(
            title="Profile Saved",
            description=f"Profile '{new_profile['name']}' has been successfully saved!",
            color=discord.Color.green()
        )
        
        await message.channel.send(embed=embed)
    
    @app_commands.command(name="list_profiles", description="List your saved checkout profiles")
    async def list_profiles(self, interaction: discord.Interaction):
        """Command to list all saved profiles for the user."""
        user_id = str(interaction.user.id)
        user_data = load_user_data(user_id)
        
        if not user_data or not user_data.get("profiles"):
            await interaction.response.send_message("You don't have any saved profiles yet.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="Your Saved Profiles",
            description="Here are your saved checkout profiles:",
            color=discord.Color.blue()
        )
        
        for profile in user_data["profiles"]:
            # Mask sensitive information
            masked_card = f"****{profile.get('card_number', '')[-4:]}" if "card_number" in profile else "Not set"
            
            profile_details = (
                f"**Name**: {profile.get('first_name', '')} {profile.get('last_name', '')}\n"
                f"**Email**: {profile.get('email', '')}\n"
                f"**Address**: {profile.get('address1', '')}, {profile.get('city', '')}\n"
                f"**Payment**: {masked_card}"
            )
            
            embed.add_field(name=profile["name"], value=profile_details, inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="delete_profile", description="Delete a saved checkout profile")
    async def delete_profile(self, interaction: discord.Interaction, profile_name: str):
        """Command to delete a saved profile."""
        user_id = str(interaction.user.id)
        user_data = load_user_data(user_id)
        
        if not user_data or not user_data.get("profiles"):
            await interaction.response.send_message("You don't have any saved profiles.", ephemeral=True)
            return
        
        # Find and remove the profile
        for i, profile in enumerate(user_data["profiles"]):
            if profile["name"] == profile_name:
                del user_data["profiles"][i]
                save_user_data(user_id, user_data)
                
                await interaction.response.send_message(f"Profile '{profile_name}' has been deleted.", ephemeral=True)
                return
        
        await interaction.response.send_message(f"Profile '{profile_name}' not found.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(ProfileCommands(bot))
