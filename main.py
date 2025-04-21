import os
import logging
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from bot import ShopifyBot
import threading
import models
from models import Setting, db
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET") or "shopify_bot_secret_key"

# Configure SQLAlchemy
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize database
db.init_app(app)

# Bot instance
bot_instance = None
bot_thread = None

def start_bot():
    """Start the Discord bot in a separate thread"""
    global bot_instance, bot_thread
    
    # Don't start a new thread if one is already running
    if bot_thread and bot_thread.is_alive():
        logger.info("Bot is already running")
        return
    
    # Get Discord token and application ID from database
    with app.app_context():
        token = Setting.get("DISCORD_TOKEN")
        app_id = Setting.get("APPLICATION_ID")
    
    if not token:
        logger.error("No Discord token found in settings.")
        return
        
    if not app_id:
        logger.warning("No Application ID found in settings.")
    
    # Update environment variables for the bot
    os.environ["DISCORD_TOKEN"] = token
    if app_id:
        os.environ["APPLICATION_ID"] = app_id
    
    # Initialize and run the bot
    bot_instance = ShopifyBot()
    
    def run_bot():
        try:
            bot_instance.run(token)
        except Exception as e:
            logger.error(f"Error running bot: {e}")
    
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    logger.info("Discord bot started in background thread")

def stop_bot():
    """Stop the Discord bot"""
    global bot_instance
    if bot_instance:
        logger.info("Stopping Discord bot...")
        bot_instance.close()
        bot_instance = None
        logger.info("Discord bot stopped")

@app.route('/')
def index():
    """Home page"""
    with app.app_context():
        token = Setting.get("DISCORD_TOKEN")
        app_id = Setting.get("APPLICATION_ID")
        bot_running = bot_thread and bot_thread.is_alive() if bot_thread else False
    
    return render_template('index.html', 
                          token=token, 
                          app_id=app_id,
                          bot_running=bot_running)

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    """Settings page"""
    if request.method == 'POST':
        discord_token = request.form.get('discord_token')
        application_id = request.form.get('application_id')
        
        with app.app_context():
            Setting.set("DISCORD_TOKEN", discord_token)
            Setting.set("APPLICATION_ID", application_id)
        
        flash('Settings saved successfully!', 'success')
        return redirect(url_for('settings'))
    
    with app.app_context():
        token = Setting.get("DISCORD_TOKEN")
        app_id = Setting.get("APPLICATION_ID")
    
    return render_template('settings.html', token=token, app_id=app_id)

@app.route('/start_bot', methods=['POST'])
def start_bot_route():
    """Start the Discord bot"""
    start_bot()
    flash('Discord bot started!', 'success')
    return redirect(url_for('index'))

@app.route('/stop_bot', methods=['POST'])
def stop_bot_route():
    """Stop the Discord bot"""
    stop_bot()
    flash('Discord bot stopped!', 'success')
    return redirect(url_for('index'))

def main():
    """Main entry point for the application."""
    load_dotenv()
    
    # Initialize the database
    with app.app_context():
        # Import models to ensure they're registered with SQLAlchemy
        from models import User, Profile, Task, Monitor, Setting
        db.create_all()
        
        # Check if token exists in database
        token = None
        try:
            token = Setting.get("DISCORD_TOKEN")
        except Exception as e:
            logger.error(f"Error checking token: {e}")
            # Tables might not exist yet, this is handled by db.create_all()
        
        # Start the bot if credentials are set
        if token:
            start_bot()
    
    # Run the Flask app
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)

if __name__ == "__main__":
    main()
