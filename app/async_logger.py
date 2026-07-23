import os
import queue
import logging
import atexit
from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler

_listener = None

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

    formatter = logging.Formatter('[%(asctime)s] %(levelname)s in %(module)s: %(message)s')
    file_handler.setFormatter(formatter)
    stream_handler.setFormatter(formatter)

    # In-memory thread-safe queue and QueueListener
    log_queue = queue.Queue(-1)
    queue_handler = QueueHandler(log_queue)

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

    app.logger.info("Asynchronous logging system initialized (QueueHandler + QueueListener).")
    return _listener
