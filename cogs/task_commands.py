import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import logging
import uuid
from typing import Dict, List, Optional
from utils.database import save_user_data, load_user_data
from utils.shopify_checkout import ShopifyCheckout

logger = logging.getLogger(__name__)

class TaskCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.checkout_tasks = {}  # Dictionary to store active checkout tasks
    
    @app_commands.command(name="add_task", description="Add a checkout task for a Shopify product")
    async def add_task(self, interaction: discord.Interaction, product_url: str, profile_name: str, 
                       quantity: int = 1, auto_checkout: bool = False):
        """Command to add a checkout task for a Shopify product."""
        user_id = str(interaction.user.id)
        user_data = load_user_data(user_id)
        
        if not user_data:
            await interaction.response.send_message(
                "You need to create a profile first. Use the `/profile` command.",
                ephemeral=True
            )
            return
        
        # Find the profile
        profile = None
        for p in user_data.get("profiles", []):
            if p["name"] == profile_name:
                profile = p
                break
        
        if not profile:
            await interaction.response.send_message(
                f"Profile '{profile_name}' not found. Please create it first with the `/profile` command.",
                ephemeral=True
            )
            return
        
        # Generate task ID
        task_id = str(uuid.uuid4())
        
        # Create task
        task = {
            "id": task_id,
            "product_url": product_url,
            "profile_name": profile_name,
            "quantity": quantity,
            "auto_checkout": auto_checkout,
            "active": True
        }
        
        # Update user data
        if "checkout_tasks" not in user_data:
            user_data["checkout_tasks"] = []
        
        user_data["checkout_tasks"].append(task)
        save_user_data(user_id, user_data)
        
        # Start the checkout task if auto_checkout is enabled
        if auto_checkout:
            checkout = ShopifyCheckout(
                product_url=product_url,
                profile=profile,
                quantity=quantity,
                bot=self.bot,
                user_id=interaction.user.id
            )
            self.checkout_tasks[task_id] = checkout
            asyncio.create_task(checkout.monitor_and_checkout())
        
        embed = discord.Embed(
            title="Checkout Task Added",
            description=f"Task created for: {product_url}",
            color=discord.Color.green()
        )
        embed.add_field(name="Task ID", value=task_id, inline=True)
        embed.add_field(name="Profile", value=profile_name, inline=True)
        embed.add_field(name="Quantity", value=str(quantity), inline=True)
        embed.add_field(name="Auto Checkout", value="Enabled" if auto_checkout else "Disabled", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="run_task", description="Run a specific checkout task")
    async def run_task(self, interaction: discord.Interaction, task_id: str):
        """Command to run a specific checkout task."""
        user_id = str(interaction.user.id)
        user_data = load_user_data(user_id)
        
        if not user_data or not user_data.get("checkout_tasks"):
            await interaction.response.send_message(
                "You don't have any checkout tasks.",
                ephemeral=True
            )
            return
        
        # Find the task
        task = None
        for t in user_data["checkout_tasks"]:
            if t["id"] == task_id and t.get("active", False):
                task = t
                break
        
        if not task:
            await interaction.response.send_message(
                f"Task with ID {task_id} not found or not active.",
                ephemeral=True
            )
            return
        
        # Find the profile
        profile = None
        for p in user_data.get("profiles", []):
            if p["name"] == task["profile_name"]:
                profile = p
                break
        
        if not profile:
            await interaction.response.send_message(
                f"Profile '{task['profile_name']}' not found. The task cannot be run.",
                ephemeral=True
            )
            return
        
        # Start the checkout process
        checkout = ShopifyCheckout(
            product_url=task["product_url"],
            profile=profile,
            quantity=task["quantity"],
            bot=self.bot,
            user_id=interaction.user.id
        )
        
        await interaction.response.send_message(
            f"Starting checkout for task {task_id}...",
            ephemeral=True
        )
        
        self.checkout_tasks[task_id] = checkout
        asyncio.create_task(checkout.checkout())
    
    @app_commands.command(name="cancel_task", description="Cancel a checkout task")
    async def cancel_task(self, interaction: discord.Interaction, task_id: str):
        """Command to cancel a checkout task."""
        user_id = str(interaction.user.id)
        user_data = load_user_data(user_id)
        
        if not user_data or not user_data.get("checkout_tasks"):
            await interaction.response.send_message(
                "You don't have any checkout tasks.",
                ephemeral=True
            )
            return
        
        # Find and update the task
        for i, task in enumerate(user_data["checkout_tasks"]):
            if task["id"] == task_id:
                user_data["checkout_tasks"][i]["active"] = False
                save_user_data(user_id, user_data)
                
                # Stop the checkout task if it's running
                if task_id in self.checkout_tasks:
                    self.checkout_tasks[task_id].stop()
                    del self.checkout_tasks[task_id]
                
                await interaction.response.send_message(
                    f"Task {task_id} has been cancelled.",
                    ephemeral=True
                )
                return
        
        await interaction.response.send_message(
            f"Task with ID {task_id} not found.",
            ephemeral=True
        )
    
    @app_commands.command(name="list_tasks", description="List all your checkout tasks")
    async def list_tasks(self, interaction: discord.Interaction):
        """Command to list all checkout tasks for the user."""
        user_id = str(interaction.user.id)
        user_data = load_user_data(user_id)
        
        if not user_data or not user_data.get("checkout_tasks"):
            await interaction.response.send_message(
                "You don't have any checkout tasks set up.",
                ephemeral=True
            )
            return
        
        # Filter active tasks
        active_tasks = [task for task in user_data["checkout_tasks"] if task.get("active", False)]
        
        if not active_tasks:
            await interaction.response.send_message(
                "You don't have any active checkout tasks.",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="Your Checkout Tasks",
            description=f"You have {len(active_tasks)} active checkout tasks:",
            color=discord.Color.blue()
        )
        
        for task in active_tasks:
            embed.add_field(
                name=f"Task ID: {task['id']}",
                value=(
                    f"URL: {task['product_url']}\n"
                    f"Profile: {task['profile_name']}\n"
                    f"Quantity: {task['quantity']}\n"
                    f"Auto Checkout: {'Enabled' if task.get('auto_checkout', False) else 'Disabled'}"
                ),
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(TaskCommands(bot))
