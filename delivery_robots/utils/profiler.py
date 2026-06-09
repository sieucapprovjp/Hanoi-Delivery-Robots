import time
import functools
import os
from typing import Dict, Any, Optional
from contextlib import contextmanager

class Profiler:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Profiler, cls).__new__(cls)
            cls._instance.stats = {}
            cls._instance.log_dir = "logs"
            cls._instance.log_file = os.path.join(cls._instance.log_dir, "performance.log")
        return cls._instance
    
    def record(self, label: str, duration: float):
        if label not in self.stats:
            self.stats[label] = {
                "count": 0,
                "total_time": 0.0,
                "max_time": 0.0,
                "avg_time": 0.0
            }
        
        stat = self.stats[label]
        stat["count"] += 1
        stat["total_time"] += duration
        stat["max_time"] = max(stat["max_time"], duration)
        stat["avg_time"] = stat["total_time"] / stat["count"]

    def get_stats(self) -> Dict[str, Any]:
        return self.stats

    def clear(self):
        self.stats = {}

    def save_to_log(self):
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
            
        with open(self.log_file, "w") as f:
            f.write("=== Performance Stats ===\n")
            f.write(f"{'Label':<40} | {'Count':<8} | {'Avg (ms)':<10} | {'Max (ms)':<10}\n")
            f.write("-" * 75 + "\n")
            for label, data in sorted(self.stats.items()):
                f.write(f"{label:<40} | {data['count']:<8} | {data['avg_time']*1000:10.4f} | {data['max_time']*1000:10.4f}\n")
            f.write("=" * 75 + "\n")
            f.write(f"Last updated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

def profile_time(label: Optional[str] = None):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            p = Profiler()
            start = time.perf_counter()
            result = func(*args, **kwargs)
            end = time.perf_counter()
            
            use_label = label or func.__name__
            p.record(use_label, end - start)
            return result
        return wrapper
    return decorator

@contextmanager
def profile_block(label: str):
    p = Profiler()
    start = time.perf_counter()
    try:
        yield
    finally:
        end = time.perf_counter()
        p.record(label, end - start)
