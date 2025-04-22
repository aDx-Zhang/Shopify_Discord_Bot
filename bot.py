import os
import time
import logging
import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import sqlite3

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ensure database directory exists
os.makedirs('instance', exist_ok=True)
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///instance/ninjabot.db')

def init_db():
    """Initialize the database if using SQLite"""
    if DATABASE_URL.startswith('sqlite'):
        conn = sqlite3.connect('instance/ninjabot.db')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS settings
                     (key TEXT PRIMARY KEY, value TEXT)''')
        conn.commit()
        conn.close()

init_db()

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
        self.start_time = time.time()
        self.active_tasks = []
        self.success_count = 0
        self.total_tasks = 0
        self.response_times = []
        
    def get_uptime(self):
        """Get bot uptime in HH:MM:SS format."""
        uptime = int(time.time() - self.start_time)
        hours = uptime // 3600
        minutes = (uptime % 3600) // 60
        seconds = uptime % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    def get_memory_usage(self):
        """Get bot memory usage in MB."""
        import psutil
        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024
    
    def get_success_rate(self):
        """Get task success rate as percentage."""
        if self.total_tasks == 0:
            return 100.0
        return (self.success_count / self.total_tasks) * 100
    
    def get_avg_response_time(self):
        """Get average response time in milliseconds."""
        if not self.response_times:
            return 0
        return sum(self.response_times) / len(self.response_times)
    
    def get_active_users(self):
        """Get list of active users."""
        return set(task.get('user_id', 0) for task in self.active_tasks)
        
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

    async def on_interaction(self, interaction: discord.Interaction):
        """Handle interaction errors."""
        if interaction.type == discord.InteractionType.application_command:
            try:
                if not interaction.response.is_done():
                    await interaction.response.defer(ephemeral=True)
            except (discord.errors.NotFound, discord.errors.HTTPException):
                pass
        
        # Set bot status
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="Shopify products"
            )
        )
