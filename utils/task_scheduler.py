
import schedule
import time
import threading

class TaskScheduler:
    def __init__(self):
        self.schedule = schedule.Scheduler()
        
    def add_task(self, task_func, trigger_time):
        self.schedule.every().day.at(trigger_time).do(task_func)
        
    def start(self):
        threading.Thread(target=self._run_continuously).start()
        
    def _run_continuously(self):
        while True:
            self.schedule.run_pending()
            time.sleep(1)
