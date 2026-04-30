"""Gunicorn configuration for production deployment."""

import os

# Server socket
bind = f"0.0.0.0:{os.environ.get('PORT', '5050')}"

# Worker processes
workers = int(os.environ.get("WEB_CONCURRENCY", "2"))
threads = 4
worker_class = "gthread"
timeout = 120

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Security
limit_request_line = 8190
limit_request_fields = 100
limit_request_field_size = 8190
