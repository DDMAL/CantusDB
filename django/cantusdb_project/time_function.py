from functools import wraps
from time import time

def time_function(fn):
    @wraps(fn)
    def measure_time(*args, **kwargs):
        t1 = time()
        result = fn(*args, **kwargs)
        t2 = time()
        print(f"@time_function: {fn.__name__} took {t2 - t1:.3f}s.")
        return result
    return measure_time
