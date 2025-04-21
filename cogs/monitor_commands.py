import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import logging
import re
from typing import Dict, List, Optional
import uuid
from utils.database import save_user_data, load_user_data
from utils.shopify_monitor import ShopifyMonitor

logger = logging.getLogger(__name__)

class MonitorCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.monitors = {}  # Dictionary to store active monitors: {monitor_id: ShopifyMonitor}
    
    @app_commands.command(name="monitor", description="Monitor a Shopify product for availability")
    async def monitor(self, interaction: discord.Interaction, product_url: str, notify: bool = True):
        """Command to start monitoring a Shopify product."""
        # Validate the URL is a Shopify URL
        if not self._is_valid_shopify_url(product_url):
            await interaction.response.send_message(
                "Invalid Shopify URL. Please provide a valid Shopify product URL.",
                ephemeral=True
            )
            return
        
        user_id = str(interaction.user.id)
        
        # Generate a unique ID for this monitoring task
        monitor_id = str(uuid.uuid4())
        
        # Create monitoring task
        monitor_task = {
            "id": monitor_id,
            "product_url": product_url,
            "notify": notify,
            "active": True
        }
        
        # Update user data with the new monitor task
        user_data = load_user_data(user_id)
        if not user_data:
            user_data = {"profiles": [], "monitoring_tasks": [], "checkout_tasks": []}
        
        user_data["monitoring_tasks"].append(monitor_task)
        save_user_data(user_id, user_data)
        
        # Start the monitor
        monitor = ShopifyMonitor(product_url, self.bot, interaction.user.id, notify)
        self.monitors[monitor_id] = monitor
        asyncio.create_task(monitor.start_monitoring())
        
        embed = discord.Embed(
            title="Monitor Started",
            description=f"Now monitoring product at: {product_url}",
            color=discord.Color.green()
        )
        embed.add_field(name="Monitor ID", value=monitor_id, inline=True)
        embed.add_field(name="Notifications", value="Enabled" if notify else "Disabled", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="stop_monitor", description="Stop monitoring a Shopify product")
    async def stop_monitor(self, interaction: discord.Interaction, monitor_id: str):
        """Command to stop monitoring a specific product."""
        user_id = str(interaction.user.id)
        user_data = load_user_data(user_id)
        
        if not user_data or not user_data.get("monitoring_tasks"):
            await interaction.response.send_message(
                "You don't have any active monitoring tasks.",
                ephemeral=True
            )
            return
        
        # Find the monitoring task
        for i, task in enumerate(user_data["monitoring_tasks"]):
            if task["id"] == monitor_id:
                # Update the task in user data
                user_data["monitoring_tasks"][i]["active"] = False
                save_user_data(user_id, user_data)
                
                # Stop the monitor if it exists
                if monitor_id in self.monitors:
                    self.monitors[monitor_id].stop_monitoring()
                    del self.monitors[monitor_id]
                
                await interaction.response.send_message(
                    f"Successfully stopped monitoring task {monitor_id}.",
                    ephemeral=True
                )
                return
        
        await interaction.response.send_message(
            f"Monitor task with ID {monitor_id} not found.",
            ephemeral=True
        )
    
    @app_commands.command(name="list_monitors", description="List all your active product monitors")
    async def list_monitors(self, interaction: discord.Interaction):
        """Command to list all active monitors for the user."""
        user_id = str(interaction.user.id)
        user_data = load_user_data(user_id)
        
        if not user_data or not user_data.get("monitoring_tasks"):
            await interaction.response.send_message(
                "You don't have any monitoring tasks set up.",
                ephemeral=True
            )
            return
        
        # Filter active tasks
        active_tasks = [task for task in user_data["monitoring_tasks"] if task.get("active", False)]
        
        if not active_tasks:
            await interaction.response.send_message(
                "You don't have any active monitoring tasks.",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="Your Active Monitors",
            description=f"You have {len(active_tasks)} active monitoring tasks:",
            color=discord.Color.blue()
        )
        
        for task in active_tasks:
            embed.add_field(
                name=f"Monitor ID: {task['id']}",
                value=f"URL: {task['product_url']}\nNotifications: {'Enabled' if task.get('notify', True) else 'Disabled'}",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    def _is_valid_shopify_url(self, url: str) -> bool:
        """Check if a URL is a valid Shopify product URL."""
        # Basic validation for Shopify URLs
        shopify_pattern = r'https?://([a-zA-Z0-9-]+)\.myshopify\.com/.*|https?://([a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)/.*products/.*'
        return bool(re.match(shopify_pattern, url))

async def setup(bot):
    await bot.add_cog(MonitorCommands(bot))
