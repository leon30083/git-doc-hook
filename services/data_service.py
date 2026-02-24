"""Data service with high complexity."""

class DataService:
    """Service for data operations."""
    
    def __init__(self, config=None):
        self.config = config or {}
        self.cache = {}
        self.connections = []
        self.metrics = {"reads": 0, "writes": 0}
    
    def get_data(self, key, default=None, timeout=30, retry=3, validate=True, refresh=False):
        """Get data with many parameters (high param count)."""
        # Many nested conditions (high nesting)
        if self.cache:
            if key in self.cache:
                if validate:
                    if refresh:
                        return self._refresh_cache(key)
                    else:
                        return self.cache[key]
                else:
                    return self.cache.get(key, default)
        
        return default
    
    def set_data(self, key, value):
        """Set data in cache."""
        self.cache[key] = value
        self.metrics["writes"] += 1
    
    def _refresh_cache(self, key):
        """Internal cache refresh."""
        return self.cache.get(key)
