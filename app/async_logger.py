import os
import queue
import logging
import atexit
import re
from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler

_listener = None

SENSITIVE_PATTERNS = [
    # Passwords & Secrets (e.g. password=..., "password": "...", parola=...)
    (re.compile(r'(?i)(password|pass|parola|sifre|şifre|secret_key|secret|api_key|token|verification_code|doğrulama_kodu)\s*[:=]\s*[\'\"]?([^\s\'\",&]+)[\'\"]?'), r'\1=[MASKED]'),
    # Credit Card Numbers (13 to 19 digits, optional spaces or dashes)
    (re.compile(r'\b(?:\d[ -]*?){13,19}\b'), lambda m: m.group(0)[:4] + '****' * 2 + m.group(0)[-4:] if len(re.sub(r'\D', '', m.group(0))) >= 13 else '[CARD_MASKED]'),
    # T.C. Identity Numbers (11 digits starting with 1-9)
    (re.compile(r'\b[1-9]\d{10}\b'), lambda m: m.group(0)[:3] + '*****' + m.group(0)[8:]),
]

def mask_sensitive_data(text):
    """
    Masks sensitive data such as passwords, TC Identity Numbers, credit card numbers, and tokens in a string.
    """
    if not isinstance(text, str):
        text = str(text)
    for pattern, repl in SENSITIVE_PATTERNS:
        text = pattern.sub(repl, text)
    return text

class SensitiveDataFilter(logging.Filter):
    """
    Filter that anonymizes sensitive information in log records before queueing/writing.
    """
    def filter(self, record):
        if isinstance(record.msg, str):
            record.msg = mask_sensitive_data(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: mask_sensitive_data(v) if isinstance(v, str) else v for k, v in record.args.items()}
            elif isinstance(record.args, (tuple, list)):
                record.args = tuple(mask_sensitive_data(arg) if isinstance(arg, str) else arg for arg in record.args)
        return True

class SensitiveDataFormatter(logging.Formatter):
    """
    Formatter that ensures the final rendered log string has all sensitive data masked.
    """
    def format(self, record):
        formatted = super().format(record)
        return mask_sensitive_data(formatted)

def init_async_logging(app):
    """
    Initializes non-blocking asynchronous logging using QueueHandler and QueueListener.
    Main application HTTP request threads put logs on an in-memory queue without disk I/O blocking.
    """
    global _listener
    if _listener is not None:
        return _listener

    log_dir = os.path.join(app.root_path, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, 'app.log')

    # Handlers that execute on background listener thread
    file_handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
    stream_handler = logging.StreamHandler()

    formatter = SensitiveDataFormatter('[%(asctime)s] %(levelname)s in %(module)s: %(message)s')
    file_handler.setFormatter(formatter)
    stream_handler.setFormatter(formatter)

    mask_filter = SensitiveDataFilter()
    file_handler.addFilter(mask_filter)
    stream_handler.addFilter(mask_filter)

    # In-memory thread-safe queue and QueueListener
    log_queue = queue.Queue(-1)
    queue_handler = QueueHandler(log_queue)
    queue_handler.addFilter(mask_filter)

    _listener = QueueListener(log_queue, file_handler, stream_handler, respect_handler_level=True)
    _listener.start()

    atexit.register(_listener.stop)

    # Attach QueueHandler to Flask app logger and root logger
    app.logger.handlers = []
    app.logger.addHandler(queue_handler)
    app.logger.setLevel(logging.INFO)

    root_logger = logging.getLogger()
    root_logger.handlers = []
    root_logger.addHandler(queue_handler)
    root_logger.setLevel(logging.INFO)

    # Suppress high-frequency third-party logs (APScheduler every minute & Werkzeug HTTP access logs)
    logging.getLogger('apscheduler').setLevel(logging.WARNING)
    logging.getLogger('werkzeug').setLevel(logging.WARNING)

    app.logger.info("Asynchronous logging system initialized (QueueHandler + QueueListener + SensitiveDataMasking).")
    return _listener


