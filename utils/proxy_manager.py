
class ProxyManager:
    def __init__(self):
        self.proxies = []
        
    def add_proxy(self, proxy):
        self.proxies.append(proxy)
        
    def get_proxy(self):
        return self.proxies[random.randint(0, len(self.proxies)-1)] if self.proxies else None
