import os
import atexit

_scheduler_lock_file = None

def init_single_worker_scheduler(app, scheduler):
    """
    Ensures Flask-APScheduler starts in ONLY ONE worker process in multi-worker environments (Gunicorn).
    Uses a cross-process non-blocking OS lock so secondary workers skip scheduler initialization.
    """
    global _scheduler_lock_file
    lock_path = os.path.join(app.root_path, 'scheduler.lock')

    try:
        lock_file = open(lock_path, 'w')
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

        _scheduler_lock_file = lock_file

        try:
            if not scheduler.running:
                scheduler.init_app(app)
        except Exception as e:
            app.logger.warning(f"Scheduler init_app warning: {e}")

        from app.jobs import check_upcoming_reservations, check_short_term_reminders
        scheduler.add_job(id='Daily Reservation Check', func=check_upcoming_reservations, args=[app], trigger='cron', hour=8, minute=0, replace_existing=True)
        scheduler.add_job(id='Short Term Reminder Check', func=check_short_term_reminders, args=[app], trigger='cron', second=0, replace_existing=True)

        if not scheduler.running:
            scheduler.start()
            app.logger.info("APScheduler successfully started in single worker process.")

        def unlock():
            global _scheduler_lock_file
            try:
                if _scheduler_lock_file:
                    _scheduler_lock_file.close()
                    _scheduler_lock_file = None
                if os.path.exists(lock_path):
                    os.remove(lock_path)
            except Exception:
                pass

        atexit.register(unlock)

    except (IOError, OSError):
        app.logger.info("APScheduler initialization skipped in this worker (another worker holds the single-worker lock).")
