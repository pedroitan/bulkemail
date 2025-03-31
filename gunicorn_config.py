import multiprocessing

bind = "0.0.0.0:8000"
workers = 2  # Minimum for Render free tier
threads = 2  # Add some threading to handle more requests
worker_class = "gthread"  # Use threads for better async performance
timeout = 120  # Increase timeout to 120 seconds (default is 30)
keepalive = 5
max_requests = 1000
max_requests_jitter = 50
