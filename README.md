# Shopify Discord Bot

A Discord bot that monitors Shopify products and automates the checkout process based on user profiles and commands.

## Features

- **Profile Management**: Save and manage multiple checkout profiles with `/profile`
- **Product Monitoring**: Monitor Shopify products for availability with `/monitor`
- **Checkout Automation**: Create and run checkout tasks with `/add_task`
- **User-Specific Data**: Each Discord user has their own profiles and tasks

## Setup Instructions

1. Clone this repository
2. Install the required packages:
   ```
   pip install discord.py requests python-dotenv aiohttp beautifulsoup4 schedule
   ```
3. Copy `.env.example` to `.env` and fill in your Discord bot token and application ID:
   ```
   DISCORD_TOKEN=your_discord_bot_token_here
   APPLICATION_ID=your_application_id_here
   ```
4. Create a Discord bot in the [Discord Developer Portal](https://discord.com/developers/applications)
   - Enable all Privileged Gateway Intents
   - Add the bot to your server with the proper permissions (bot, applications.commands)

5. Run the bot:
   ```
   python main.py
   ```

## Available Commands

- `/start` - Start using the Shopify bot
- `/profile <profile_name>` - Create a checkout profile
- `/list_profiles` - List your saved profiles
- `/delete_profile <profile_name>` - Delete a saved profile
- `/monitor <product_url> [notify]` - Monitor a Shopify product
- `/stop_monitor <monitor_id>` - Stop monitoring a product
- `/list_monitors` - List your active monitors
- `/add_task <product_url> <profile_name> [quantity] [auto_checkout]` - Add a checkout task
- `/run_task <task_id>` - Run a specific checkout task
- `/cancel_task <task_id>` - Cancel a checkout task
- `/list_tasks` - List your checkout tasks

## Security Notes

- All sensitive user data is stored locally in the `user_data` directory
- Card information is stored for checkout purposes, so ensure the host environment is secure
- The bot uses Discord's ephemeral messages for sensitive information when possible

## Limitations

- The checkout process is simplified and may not work on all Shopify stores
- Payment processing requires manual completion for security reasons
- Handling of certain edge cases (like CAPTCHA) is not implemented

## Disclaimer

This bot is provided for educational purposes only. Please use responsibly and in accordance with Shopify's Terms of Service and the terms of service for any Shopify stores you interact with.
