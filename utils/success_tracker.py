
class SuccessTracker:
    def __init__(self):
        self.total_attempts = 0
        self.successful_attempts = 0
        
    def log_attempt(self, success: bool):
        self.total_attempts += 1
        if success:
            self.successful_attempts += 1
            
    def get_success_rate(self):
        return (self.successful_attempts / self.total_attempts * 100) if self.total_attempts > 0 else 0
