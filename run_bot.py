import os
import logging
from dotenv import load_dotenv
from bot import ShopifyBot
from models import Setting, db
import threading
from flask import Flask

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create a minimal Flask app for the database connection
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

def main():
    """Main entry point for running just the bot."""
    load_dotenv()
    
    # Initialize the database
    with app.app_context():
        # Import models to ensure they're registered with SQLAlchemy
        from models import User, Profile, Task, Monitor, Setting
        db.create_all()
        
        # Check if token exists in database or .env
        token = os.getenv("DISCORD_TOKEN")
        app_id = os.getenv("APPLICATION_ID")
        
        if not token:
            # Try to get from database
            try:
                token = Setting.get("DISCORD_TOKEN")
                app_id = Setting.get("APPLICATION_ID")
            except Exception as e:
                logger.error(f"Error checking token: {e}")
        
        if not token:
            logger.error("No Discord token found. Please set DISCORD_TOKEN in .env file or database.")
            return
        
        # Update environment variables for the bot
        os.environ["DISCORD_TOKEN"] = token
        if app_id:
            os.environ["APPLICATION_ID"] = app_id
        
        # Initialize and run the bot
        bot = ShopifyBot()
        try:
            logger.info("Starting Discord bot...")
            bot.run(token)
        except Exception as e:
            logger.error(f"Error running bot: {e}")

if __name__ == "__main__":
    main()