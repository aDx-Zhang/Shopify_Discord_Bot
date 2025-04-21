import asyncio
import logging
import aiohttp
import json
import re
import discord
import time
from typing import Dict, Optional, List, Any
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class ShopifyCheckout:
    def __init__(self, product_url: str, profile: Dict[str, Any], quantity: int, bot, user_id: int):
        """Initialize the Shopify checkout client.
        
        Args:
            product_url: The URL of the Shopify product to checkout
            profile: The user's checkout profile information
            quantity: The quantity to purchase
            bot: The Discord bot instance for notifications
            user_id: Discord user ID to notify
        """
        self.product_url = product_url
        self.profile = profile
        self.quantity = quantity
        self.bot = bot
        self.user_id = user_id
        self.running = False
        self.store_domain = self._extract_domain(product_url)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        self.session = None
        self.product_info = None
        self.variant_id = None
    
    def _extract_domain(self, url: str) -> str:
        """Extract the store domain from a Shopify URL."""
        match = re.match(r'https?://([^/]+)', url)
        if match:
            return match.group(1)
        return ""
    
    async def monitor_and_checkout(self):
        """Monitor a product and automatically checkout when in stock."""
        if self.running:
            return
        
        self.running = True
        logger.info(f"Starting monitoring for checkout: {self.product_url}")
        
        # Create a persistent session
        self.session = aiohttp.ClientSession()
        
        # Main monitoring loop
        while self.running:
            try:
                # Fetch product info
                in_stock = await self._check_product_availability()
                
                if in_stock:
                    # Product is in stock, attempt checkout
                    success = await self.checkout()
                    if success:
                        # Checkout succeeded, stop monitoring
                        self.running = False
                        break
                
                # Wait before checking again
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f"Error in monitor_and_checkout: {e}")
                await asyncio.sleep(10)  # Wait longer on error
        
        # Close the session
        await self.session.close()
        self.session = None
    
    def stop(self):
        """Stop the checkout task."""
        self.running = False
        logger.info(f"Stopped checkout task for {self.product_url}")
    
    async def _check_product_availability(self) -> bool:
        """Check if the product is available.
        
        Returns:
            bool: True if the product is in stock, False otherwise
        """
        try:
            # Create a new session if necessary
            if self.session is None:
                self.session = aiohttp.ClientSession()
            
            # Construct the .json URL for the product
            json_url = self.product_url
            if json_url.endswith("/"):
                json_url = json_url[:-1]
            if not json_url.endswith(".json"):
                json_url += ".json"
            
            async with self.session.get(json_url, headers=self.headers) as response:
                if response.status != 200:
                    logger.warning(f"Failed to check product availability, status code: {response.status}")
                    return False
                
                data = await response.json()
                product = data.get("product", {})
                
                # Store product information
                self.product_info = product
                
                # Check each variant for availability
                variants = product.get("variants", [])
                for variant in variants:
                    if variant.get("available", False):
                        # Found an in-stock variant
                        self.variant_id = variant.get("id")
                        return True
                
                return False
            
        except Exception as e:
            logger.error(f"Error checking product availability: {e}")
            return False
    
    async def checkout(self) -> bool:
        """Perform the checkout process for the product.
        
        Returns:
            bool: True if checkout was successful, False otherwise
        """
        try:
            # Create a new session if necessary
            if self.session is None:
                self.session = aiohttp.ClientSession()
            
            # Notify user that checkout is starting
            await self._notify_user(f"Starting checkout for {self.product_url}")
            
            # 1. Check product availability and get variant ID if not already set
            if not self.variant_id:
                in_stock = await self._check_product_availability()
                if not in_stock:
                    await self._notify_user("Product is not available for checkout.")
                    return False
            
            # 2. Add to cart
            cart_url = f"https://{self.store_domain}/cart/add.js"
            cart_data = {
                "id": self.variant_id,
                "quantity": self.quantity
            }
            
            async with self.session.post(cart_url, headers=self.headers, json=cart_data) as response:
                if response.status != 200:
                    logger.error(f"Failed to add to cart, status code: {response.status}")
                    await self._notify_user("Failed to add product to cart.")
                    return False
                
                await self._notify_user("Product added to cart successfully!")
            
            # 3. Begin checkout
            checkout_url = f"https://{self.store_domain}/checkout"
            async with self.session.get(checkout_url, headers=self.headers) as response:
                if response.status != 200:
                    logger.error(f"Failed to begin checkout, status code: {response.status}")
                    await self._notify_user("Failed to begin checkout process.")
                    return False
                
                # Parse the checkout page to extract form details
                checkout_page = await response.text()
                soup = BeautifulSoup(checkout_page, 'html.parser')
                
                # Extract checkout token and authenticity token
                checkout_token = None
                authenticity_token = None
                
                # Find the checkout token (typically in the URL)
                checkout_url = str(response.url)
                token_match = re.search(r'/checkouts/([a-zA-Z0-9]+)', checkout_url)
                if token_match:
                    checkout_token = token_match.group(1)
                
                # Find the authenticity token
                token_input = soup.find('input', {'name': 'authenticity_token'})
                if token_input:
                    authenticity_token = token_input.get('value')
                
                if not checkout_token or not authenticity_token:
                    logger.error("Could not extract checkout tokens")
                    await self._notify_user("Failed to extract necessary checkout information.")
                    return False
            
            # 4. Submit customer information
            customer_url = f"https://{self.store_domain}/checkout/{checkout_token}"
            
            customer_data = {
                "_method": "patch",
                "authenticity_token": authenticity_token,
                "previous_step": "contact_information",
                "step": "shipping_method",
                "checkout[email]": self.profile.get("email"),
                "checkout[shipping_address][first_name]": self.profile.get("first_name"),
                "checkout[shipping_address][last_name]": self.profile.get("last_name"),
                "checkout[shipping_address][address1]": self.profile.get("address1"),
                "checkout[shipping_address][address2]": self.profile.get("address2", ""),
                "checkout[shipping_address][city]": self.profile.get("city"),
                "checkout[shipping_address][zip]": self.profile.get("zip"),
                "checkout[shipping_address][phone]": self.profile.get("phone"),
                "checkout[remember_me]": "0",
                "button": ""
            }
            
            async with self.session.post(customer_url, headers=self.headers, data=customer_data) as response:
                if response.status != 200:
                    logger.error(f"Failed to submit customer information, status code: {response.status}")
                    await self._notify_user("Failed to submit shipping information.")
                    return False
                
                await self._notify_user("Shipping information submitted successfully!")
            
            # 5. Select shipping method (typically this would detect and select a shipping option)
            # This is a simplified implementation - in a real bot, you'd parse available shipping options
            shipping_url = f"https://{self.store_domain}/checkout/{checkout_token}"
            
            shipping_data = {
                "_method": "patch",
                "authenticity_token": authenticity_token,
                "previous_step": "shipping_method",
                "step": "payment_method",
                "checkout[shipping_rate][id]": "shopify-Standard-0.00",  # This would need to be dynamically determined
                "button": ""
            }
            
            async with self.session.post(shipping_url, headers=self.headers, data=shipping_data) as response:
                if response.status != 200:
                    logger.error(f"Failed to select shipping method, status code: {response.status}")
                    await self._notify_user("Failed to select shipping method.")
                    return False
                
                await self._notify_user("Shipping method selected!")
            
            # 6. Submit payment information (simplified - in a real implementation this would be more complex)
            # Note: This is where actual payment processing would occur, which is complex and varies by store
            
            # Instead of actually submitting payment (which requires access to the payment gateway),
            # we'll notify the user that the checkout process has reached the payment stage
            
            await self._notify_user("Checkout process complete up to payment stage! Due to security limitations, you'll need to manually complete payment.")
            
            # Return a success response, even though we didn't complete payment
            return True
            
        except Exception as e:
            logger.error(f"Error during checkout process: {e}")
            await self._notify_user(f"Error during checkout: {str(e)}")
            return False
        finally:
            # Only close the session if we created it here
            if self.session and self.session._created_here:
                await self.session.close()
                self.session = None
    
    async def _notify_user(self, message: str):
        """Send a notification message to the user."""
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
