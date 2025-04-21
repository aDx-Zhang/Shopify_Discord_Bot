import asyncio
import logging
import aiohttp
import json
import re
import discord
import time
from typing import Dict, Optional, List, Union
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

async def send_restock_notification(bot, user_id, product_url, quantity):
    user = await bot.fetch_user(user_id)
    embed = discord.Embed(
        title="Product Restocked!",
        description=f"Product {product_url} is back in stock!\nQuantity: {quantity}",
        color=discord.Color.green()
    )
    await user.send(embed=embed)

class ShopifyMonitor:
    def __init__(self, product_url: str, bot, user_id: int, notify: bool = True):
        """Initialize the Shopify product monitor.
        
        Args:
            product_url: The URL of the Shopify product to monitor
            bot: The Discord bot instance
            user_id: Discord user ID to notify
            notify: Whether to send notifications when product status changes
        """
        self.product_url = product_url
        self.bot = bot
        self.user_id = user_id
        self.notify = notify
        self.running = False
        self.check_interval = 10  # seconds between checks
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0"
        }
        self.product_info = None
        self.variants = []
        self.last_stock_status = {}
    
    async def start_monitoring(self):
        """Start monitoring the Shopify product."""
        if self.running:
            return
        
        self.running = True
        logger.info(f"Starting monitor for {self.product_url}")
        
        # Get initial product info
        success = await self._fetch_product_info()
        if not success:
            await self._notify_user(f"Failed to fetch initial product information for {self.product_url}")
            self.running = False
            return
        
        # Initial notification with product details
        await self._notify_user(f"Started monitoring: {self.product_info.get('title', 'Unknown Product')}")
        
        # Main monitoring loop
        while self.running:
            try:
                await self._check_product_availability()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(self.check_interval * 2)  # Wait longer on error
    
    def stop_monitoring(self):
        """Stop monitoring the product."""
        self.running = False
        logger.info(f"Stopped monitor for {self.product_url}")
    
    async def _fetch_product_info(self) -> bool:
        """Fetch product information from the Shopify store.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.product_url, headers=self.headers) as response:
                    if response.status != 200:
                        logger.error(f"Failed to fetch product, status code: {response.status}")
                        return False
                    
                    html = await response.text()
                    
                    # Parse the JSON data from the page
                    json_match = re.search(r'var meta = (.*?);\n', html)
                    if not json_match:
                        logger.error("Could not find product metadata in the page")
                        return False
                    
                    product_json = json.loads(json_match.group(1))
                    
                    # Extract product info
                    self.product_info = {
                        "title": product_json.get("product", {}).get("title", "Unknown"),
                        "handle": product_json.get("product", {}).get("handle", ""),
                        "vendor": product_json.get("product", {}).get("vendor", ""),
                        "type": product_json.get("product", {}).get("type", ""),
                        "url": self.product_url
                    }
                    
                    # Get variant information
                    soup = BeautifulSoup(html, 'html.parser')
                    variants_json = None
                    
                    # Look for variants in JSON data
                    variants_match = re.search(r'var meta = ({.*?"variants":\s*\[.*?\]})', html)
                    if variants_match:
                        try:
                            variants_data = json.loads(variants_match.group(1))
                            variants_json = variants_data.get("product", {}).get("variants", [])
                        except (json.JSONDecodeError, KeyError) as e:
                            logger.error(f"Error parsing variants JSON: {e}")
                    
                    # If we found variants JSON, extract details
                    if variants_json:
                        self.variants = []
                        for variant in variants_json:
                            self.variants.append({
                                "id": variant.get("id"),
                                "title": variant.get("title"),
                                "price": variant.get("price"),
                                "available": variant.get("available", False),
                                "option1": variant.get("option1"),
                                "option2": variant.get("option2"),
                                "option3": variant.get("option3")
                            })
                            
                            # Initialize last stock status
                            if variant.get("id"):
                                self.last_stock_status[variant.get("id")] = variant.get("available", False)
                    
                    return True
            
        except Exception as e:
            logger.error(f"Error fetching product info: {e}")
            return False
    
    async def _check_product_availability(self):
        """Check the current availability of the product and its variants."""
        try:
            # Construct the .json URL for the product
            json_url = self.product_url
            if json_url.endswith("/"):
                json_url = json_url[:-1]
            if not json_url.endswith(".json"):
                json_url += ".json"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(json_url, headers=self.headers) as response:
                    if response.status != 200:
                        logger.warning(f"Failed to check product availability, status code: {response.status}")
                        return
                    
                    data = await response.json()
                    product = data.get("product", {})
                    
                    # Check each variant for stock changes
                    variants = product.get("variants", [])
                    product_title = product.get("title", "Unknown Product")
                    
                    for variant in variants:
                        variant_id = variant.get("id")
                        variant_title = variant.get("title")
                        available = variant.get("available", False)
                        
                        # If this is a new variant or the availability has changed
                        if variant_id not in self.last_stock_status or self.last_stock_status[variant_id] != available:
                            self.last_stock_status[variant_id] = available
                            
                            if available and self.notify:
                                # Product is now in stock
                                await self._notify_restock(product_title, variant_title, variant_id)
                            elif not available and self.notify and variant_id in self.last_stock_status:
                                # Product is now out of stock
                                await self._notify_user(f"{product_title} ({variant_title}) is now out of stock.")
        
        except Exception as e:
            logger.error(f"Error checking product availability: {e}")
    
    async def _notify_restock(self, product_title: str, variant_title: str, variant_id: str):
        """Send a restock notification to the user."""
        user = self.bot.get_user(self.user_id)
        if not user:
            logger.warning(f"Could not find user with ID {self.user_id}")
            return
        
        # Create an embed with product details
        embed = discord.Embed(
            title="🚨 Product In Stock!",
            description=f"**{product_title}**\nVariant: {variant_title}",
            color=discord.Color.green(),
            url=self.product_url
        )
        
        embed.add_field(name="Status", value="In Stock!", inline=True)
        embed.add_field(name="Action", value="Use `/add_task` to checkout", inline=True)
        embed.set_footer(text=f"Monitored by Shopify Bot | {time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        try:
            await user.send(embed=embed)
        except discord.errors.Forbidden:
            logger.warning(f"Cannot send DM to user {self.user_id}")
        except Exception as e:
            logger.error(f"Error sending restock notification: {e}")
    
    async def _notify_user(self, message: str):
        """Send a notification message to the user."""
        if not self.notify:
            return
        
        user = self.bot.get_user(self.user_id)
        if not user:
            logger.warning(f"Could not find user with ID {self.user_id}")
            return
        
        try:
            await user.send(message)
        except discord.errors.Forbidden:
            logger.warning(f"Cannot send DM to user {self.user_id}")
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
