
class ErrorHandler:
    def __init__(self):
        self.retry_count = 3
        self.retry_delay = 5
        
    async def handle_checkout_error(self, checkout_func, *args):
        for attempt in range(self.retry_count):
            try:
                return await checkout_func(*args)
            except Exception as e:
                if attempt == self.retry_count - 1:
                    raise e
                await asyncio.sleep(self.retry_delay)
