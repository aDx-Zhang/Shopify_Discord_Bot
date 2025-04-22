import os
import logging

from flask_sock import Sock

from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from bot import ShopifyBot
import threading
import models
from models import Setting, Task, Profile, db
import json

from datetime import datetime

# Configure logging
class WebSocketLogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.clients = set()
        
    def emit(self, record):
        msg = self.format(record)
        dead_clients = set()
        
        for client in self.clients:
            try:
                log_entry = {
                    'timestamp': datetime.now().strftime('%H:%M:%S'),
                    'level': record.levelname.lower(),
                    'message': msg
                }
                client.send(json.dumps(log_entry))
            except Exception as e:
                print(f"Error sending log: {e}")
                dead_clients.add(client)
        
        self.clients.difference_update(dead_clients)

# Create custom handler for werkzeug logs
class WerkzeugLogHandler(logging.Handler):
    def __init__(self, ws_handler):
        super().__init__()
        self.ws_handler = ws_handler
        
    def emit(self, record):
        self.ws_handler.emit(record)

ws_handler = WebSocketLogHandler()
ws_handler.setFormatter(logging.Formatter('%(name)s - %(levelname)s - %(message)s'))

# Configure logging for all loggers
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        ws_handler
    ])

# Add handler to werkzeug logger
werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.addHandler(WerkzeugLogHandler(ws_handler))

logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET") or "shopify_bot_secret_key"
sock = Sock(app)

@sock.route('/ws/logs')
def logs_socket(ws):
    try:
        ws_handler.clients.add(ws)
        logger.info("WebSocket client connected")
        while True:
            # Keep connection alive
            ws.receive()
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        ws_handler.clients.discard(ws)
        logger.info("WebSocket client disconnected")

# Load environment variables
load_dotenv()

# Configure SQLAlchemy
database_url = os.environ.get("DATABASE_URL")

# If DATABASE_URL is not set, use a default SQLite database
if not database_url:
    logger.warning("DATABASE_URL not set. Using SQLite as default.")
    database_url = 'sqlite:///ninjabot.db'  # Local SQLite database

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
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
    try:
        app_id = int(app_id) if app_id else None
        bot_instance = ShopifyBot()
        
        def run_bot():
            try:
                bot_instance.run(token)
            except Exception as e:
                logger.error(f"Error running bot: {e}")
                
    except Exception as e:
        logger.error(f"Error initializing bot: {e}")
        return

    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    logger.info("Discord bot started in background thread")


def stop_bot():
    """Stop the Discord bot"""
    global bot_instance
    if bot_instance:
        logger.info("Stopping Discord bot...")
        try:
            asyncio.run_coroutine_threadsafe(bot_instance.close(), bot_instance.loop)
            bot_instance = None
            logger.info("Discord bot stopped")
        except Exception as e:
            logger.error(f"Error stopping bot: {e}")




@app.route('/api/tasks')
def get_tasks():
    """Get all tasks from both database and user_data files"""
    try:
        tasks = []
        # Get tasks from user_data files
        user_data_dir = 'user_data'
        if os.path.exists(user_data_dir):
            for filename in os.listdir(user_data_dir):
                if filename.endswith('.json'):
                    with open(os.path.join(user_data_dir, filename)) as f:
                        user_data = json.load(f)
                        if 'checkout_tasks' in user_data:
                            for task in user_data['checkout_tasks']:
                                if task.get('active', True):  # Only include active tasks
                                    tasks.append({
                                        'id': task['id'],
                                        'product_url': task['product_url'],
                                        'quantity': task.get('quantity', 1),
                                        'active': True,
                                        'profile_name': task.get('profile_name', 'N/A')
                                    })

        # Also get tasks from database
        with app.app_context():
            db_tasks = Task.query.all()
            for task in db_tasks:
                profile = Profile.query.get(task.profile_id)
                profile_name = profile.name if profile else 'N/A'
                tasks.append({
                    'id': task.task_id,
                    'product_url': task.product_url,
                    'quantity': task.quantity,
                    'active': task.active,
                    'profile_name': profile_name
                })
                
        logger.info(f"Fetched {len(tasks)} tasks")
        return jsonify(tasks)
    except Exception as e:
        logger.error(f"Error fetching tasks: {e}")
        return jsonify([])


@app.route('/')
def index():
    """Home page"""
    with app.app_context():
        token = Setting.get("DISCORD_TOKEN")
        app_id = Setting.get("APPLICATION_ID")
        bot_running = bot_thread and bot_thread.is_alive(
        ) if bot_thread else False

    return render_template('index.html',
                           token=token,
                           app_id=app_id,
                           bot_running=bot_running)


async def init_bot():
    """Initialize the Discord bot"""
    bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())
    
    # Load all cogs
    cogs = ['price_commands', 'store_commands', 'task_commands', 
            'profile_commands', 'monitor_commands']
    
    for cog in cogs:
        try:
            await bot.load_extension(f'cogs.{cog}')
            logger.info(f"Loaded extension: {cog}")
        except Exception as e:
            logger.error(f"Failed to load extension {cog}: {e}")
    
    return bot

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

@app.route('/api/stats')
def get_stats():
    """Get real-time statistics"""
    if bot_instance:
        stats = {
            'uptime': bot_instance.get_uptime(),
            'activeTasks': len(bot_instance.active_tasks) if hasattr(bot_instance, 'active_tasks') else 0,
            'memoryUsage': f"{bot_instance.get_memory_usage():.1f}MB",
            'successRate': f"{bot_instance.get_success_rate():.1f}%",
            'avgResponse': f"{bot_instance.get_avg_response_time():.0f}ms",
            'activeUsers': len(bot_instance.get_active_users()) if hasattr(bot_instance, 'get_active_users') else 0
        }
    else:
        stats = {
            'uptime': '0:00:00',
            'activeTasks': 0,
            'memoryUsage': '0MB',
            'successRate': '0%',
            'avgResponse': '0ms',
            'activeUsers': 0
        }
    return jsonify(stats)

@app.route('/refresh_monitors')
def refresh_monitors():
    """Refresh all monitors"""
    if bot_instance:
        return jsonify({'success': True, 'monitors': bot_instance.get_monitors_status()})
    return jsonify({'success': False, 'error': 'Bot not running'})

@app.route('/clear_tasks', methods=['POST'])
def clear_tasks():
    """Clear all tasks"""
    if bot_instance:
        bot_instance.clear_tasks()
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Bot not running'})

@app.route('/analytics')
def analytics():
    """Analytics page"""
    return render_template('analytics.html')


def main():
    """Main entry point for the application."""
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
