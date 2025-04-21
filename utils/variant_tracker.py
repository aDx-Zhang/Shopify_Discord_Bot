
import aiohttp
import logging
import json
import asyncio
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class VariantTracker:
    def __init__(self):
        self.variants_cache = {}
        self.last_check = {}
        self.rate_limit_delay = 1  # seconds between requests
        
    async def fetch_variants(self, product_url: str) -> Optional[List[Dict]]:
        """Fetch variants for a product with rate limiting."""
        # Respect rate limiting
        now = datetime.now()
        if product_url in self.last_check:
            time_diff = (now - self.last_check[product_url]).total_seconds()
            if time_diff < self.rate_limit_delay:
                await asyncio.sleep(self.rate_limit_delay - time_diff)
        
        try:
            # Convert URL to .json if needed
            if not product_url.endswith('.json'):
                product_url = product_url.rstrip('/') + '.json'
            
            async with aiohttp.ClientSession() as session:
                async with session.get(product_url) as response:
                    if response.status == 429:  # Rate limited
                        logger.warning(f"Rate limited while fetching variants for {product_url}")
                        await asyncio.sleep(5)  # Wait longer when rate limited
                        return None
                        
                    if response.status != 200:
                        logger.error(f"Failed to fetch variants: {response.status}")
                        return None
                        
                    data = await response.json()
                    variants = data.get('product', {}).get('variants', [])
                    
                    # Update cache
                    self.variants_cache[product_url] = variants
                    self.last_check[product_url] = now
                    
                    return variants
                    
        except Exception as e:
            logger.error(f"Error fetching variants: {e}")
            return None
            
    async def track_changes(self, product_url: str) -> Optional[Dict]:
        """Track changes in variants compared to last check."""
        current_variants = await self.fetch_variants(product_url)
        if not current_variants:
            return None
            
        changes = {
            'new_variants': [],
            'removed_variants': [],
            'price_changes': [],
            'stock_changes': []
        }
        
        # Get previous variants
        previous_variants = self.variants_cache.get(product_url, [])
        
        # Convert to dict for easier comparison
        current_dict = {str(v['id']): v for v in current_variants}
        previous_dict = {str(v['id']): v for v in previous_variants}
        
        # Check for new and removed variants
        current_ids = set(current_dict.keys())
        previous_ids = set(previous_dict.keys())
        
        new_ids = current_ids - previous_ids
        removed_ids = previous_ids - current_ids
        
        changes['new_variants'] = [current_dict[id] for id in new_ids]
        changes['removed_variants'] = [previous_dict[id] for id in removed_ids]
        
        # Check for price and stock changes
        for variant_id in current_ids & previous_ids:
            current = current_dict[variant_id]
            previous = previous_dict[variant_id]
            
            if current.get('price') != previous.get('price'):
                changes['price_changes'].append({
                    'variant_id': variant_id,
                    'old_price': previous.get('price'),
                    'new_price': current.get('price')
                })
                
            if current.get('available') != previous.get('available'):
                changes['stock_changes'].append({
                    'variant_id': variant_id,
                    'title': current.get('title'),
                    'available': current.get('available')
                })
                
        return changes if any(changes.values()) else None

    async def get_variant_details(self, product_url: str, variant_id: str) -> Optional[Dict]:
        """Get detailed information about a specific variant."""
        variants = await self.fetch_variants(product_url)
        if not variants:
            return None
            
        for variant in variants:
            if str(variant.get('id')) == str(variant_id):
                return variant
                
        return None
