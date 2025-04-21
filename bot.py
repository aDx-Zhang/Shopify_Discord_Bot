import os
import logging
import discord
from discord import app_commands
from discord.ext import commands
import asyncio

logger = logging.getLogger(__name__)

class ShopifyBot(commands.Bot):
    def __init__(self):
        """Initialize the Shopify Discord bot."""
        intents = discord.Intents.default()
        intents.message_content = True
        
        application_id = os.getenv("APPLICATION_ID")
        try:
            application_id = int(application_id) if application_id else None
        except ValueError:
            application_id = None
            
        super().__init__(
            command_prefix="/",
            intents=intents,
            application_id=application_id
        )
        
        # Initialize bot state
        self.synced = False
        
    async def setup_hook(self):
        """Load all cogs when the bot starts."""
        await self.load_cogs()
        logger.info("Bot setup completed")
    
    async def load_cogs(self):
        """Load all command cogs."""
        for filename in os.listdir("./cogs"):
            if filename.endswith(".py"):
                try:
                    await self.load_extension(f"cogs.{filename[:-3]}")
                    logger.info(f"Loaded extension: {filename[:-3]}")
                except Exception as e:
                    logger.error(f"Failed to load extension {filename}: {e}")
    
    async def on_ready(self):
        """Event triggered when the bot is ready and connected to Discord."""
        await self.wait_until_ready()
        
        if not self.synced:
            # Sync slash commands with Discord
            await self.tree.sync()
            self.synced = True
            
        logger.info(f"Bot is ready! Logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Connected to {len(self.guilds)} guilds")
        
        # Set bot status
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="Shopify products"
            )
        )
