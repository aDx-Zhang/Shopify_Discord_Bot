
import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import uuid
import logging
from utils.database import save_user_data, load_user_data
from utils.shopify_monitor import ShopifyMonitor

logger = logging.getLogger(__name__)

class PriceCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.alerts = {}
        self.monitoring_tasks = {}
        
    async def monitor_price(self, alert_id: str, user_id: str, product_url: str, target_price: float):
        """Monitor product price and alert when target is reached."""
        monitor = ShopifyMonitor(product_url, self.bot, int(user_id))
        
        while True:
            try:
                success = await monitor._fetch_product_info()
                if success and monitor.variants:
                    current_price = float(monitor.variants[0].get('price', 0))
                    
                    if current_price <= target_price:
                        user = await self.bot.fetch_user(int(user_id))
                        embed = discord.Embed(
                            title="🎯 Price Target Reached!",
                            description=f"Product price has reached your target!\nCurrent Price: ${current_price}\nTarget Price: ${target_price}",
                            color=discord.Color.green(),
                            url=product_url
                        )
                        await user.send(embed=embed)
                        
                        # Deactivate alert
                        user_data = load_user_data(user_id)
                        for alert in user_data.get("price_alerts", []):
                            if alert["id"] == alert_id:
                                alert["active"] = False
                                break
                        save_user_data(user_id, user_data)
                        return
                        
            except Exception as e:
                logger.error(f"Error monitoring price: {e}")
            
            await asyncio.sleep(60)  # Check every minute

    @app_commands.command(name="price_alert", description="Set a price alert for a product")
    async def price_alert(self, interaction: discord.Interaction, product_url: str, target_price: float):
        user_id = str(interaction.user.id)
        alert_id = str(uuid.uuid4())
        
        alert = {
            "id": alert_id,
            "product_url": product_url,
            "target_price": target_price,
            "active": True
        }
        
        user_data = load_user_data(user_id)
        if not user_data:
            user_data = {}
        if "price_alerts" not in user_data:
            user_data["price_alerts"] = []
        
        user_data["price_alerts"].append(alert)
        save_user_data(user_id, user_data)
        
        # Start monitoring task
        task = asyncio.create_task(self.monitor_price(alert_id, user_id, product_url, target_price))
        self.monitoring_tasks[alert_id] = task
        
        embed = discord.Embed(
            title="Price Alert Set",
            description=f"I'll notify you when the price drops to ${target_price} or below.",
            color=discord.Color.blue()
        )
        embed.add_field(name="Product URL", value=product_url)
        embed.add_field(name="Alert ID", value=alert_id)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="list_alerts", description="List your active price alerts")
    async def list_alerts(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        user_data = load_user_data(user_id)
        
        if not user_data or "price_alerts" not in user_data:
            await interaction.response.send_message("You don't have any price alerts.", ephemeral=True)
            return
            
        active_alerts = [alert for alert in user_data["price_alerts"] if alert.get("active", True)]
        
        if not active_alerts:
            await interaction.response.send_message("You don't have any active price alerts.", ephemeral=True)
            return
            
        embed = discord.Embed(
            title="Your Price Alerts",
            description=f"You have {len(active_alerts)} active price alerts:",
            color=discord.Color.blue()
        )
        
        for alert in active_alerts:
            embed.add_field(
                name=f"Alert ID: {alert['id']}",
                value=f"URL: {alert['product_url']}\nTarget Price: ${alert['target_price']}",
                inline=False
            )
            
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="cancel_alert", description="Cancel a price alert")
    async def cancel_alert(self, interaction: discord.Interaction, alert_id: str):
        user_id = str(interaction.user.id)
        user_data = load_user_data(user_id)
        
        if not user_data or "price_alerts" not in user_data:
            await interaction.response.send_message("Alert not found.", ephemeral=True)
            return
            
        for alert in user_data["price_alerts"]:
            if alert["id"] == alert_id:
                alert["active"] = False
                save_user_data(user_id, user_data)
                
                # Cancel monitoring task
                if alert_id in self.monitoring_tasks:
                    self.monitoring_tasks[alert_id].cancel()
                    del self.monitoring_tasks[alert_id]
                
                await interaction.response.send_message(f"Price alert {alert_id} cancelled.", ephemeral=True)
                return
                
        await interaction.response.send_message("Alert not found.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(PriceCommands(bot))
