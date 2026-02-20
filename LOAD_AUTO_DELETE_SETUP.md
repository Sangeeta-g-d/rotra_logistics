# Auto-Delete Unassigned Loads Setup Guide

This guide explains how to automatically delete loads that have no driver assigned after 2 days.

## Overview

Two solutions are provided:

1. **Management Command** (Simple, manual or cron-based)
2. **Celery Task** (Automated, requires Celery setup)

---

## Option 1: Management Command (Recommended for simple setup)

### Run Manually
```bash
# Preview what will be deleted (dry-run mode)
python manage.py delete_unassigned_loads --dry-run

# Delete unassigned loads older than 2 days
python manage.py delete_unassigned_loads

# Delete unassigned loads older than 7 days
python manage.py delete_unassigned_loads --days 7
```

### Schedule with Cron (Linux/Mac)

1. Open crontab editor:
   ```bash
   crontab -e
   ```

2. Add this line to run daily at 2 AM:
   ```bash
   0 2 * * * cd /path/to/rotra_logistics && python manage.py delete_unassigned_loads
   ```

3. To run every 6 hours:
   ```bash
   0 */6 * * * cd /path/to/rotra_logistics && python manage.py delete_unassigned_loads
   ```

### Schedule with Task Scheduler (Windows)

1. Open Task Scheduler
2. Create Basic Task → Name it "Delete Unassigned Loads"
3. Trigger: Daily at 2:00 AM
4. Action: Start a program
   - Program: `C:\path\to\python.exe`
   - Arguments: `manage.py delete_unassigned_loads`
   - Start in: `C:\path\to\rotra_logistics\`

---

## Option 2: Celery Periodic Task (Advanced - Auto-runs)

### Prerequisites
Make sure Celery is installed:
```bash
pip install celery
```

### Setup Steps

1. **Configure Celery in settings.py:**

Add these settings at the end of your `rotra_logistics/settings.py`:

```python
# Celery Configuration
CELERY_BROKER_URL = 'redis://localhost:6379/0'  # or 'amqp://guest:guest@localhost//'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'

# Celery Beat Schedule (periodic tasks)
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'delete-old-unassigned-loads': {
        'task': 'logistics_app.tasks.delete_old_unassigned_loads',
        'schedule': crontab(hour=2, minute=0),  # Run daily at 2 AM
        'args': (2,)  # Delete loads older than 2 days
    },
}
```

2. **Create `rotra_logistics/celery.py`:**

```python
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rotra_logistics.settings')

app = Celery('rotra_logistics')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
```

3. **Update `rotra_logistics/__init__.py`:**

```python
from .celery import app as celery_app

__all__ = ('celery_app',)
```

4. **Run Celery Worker and Beat:**

Terminal 1 (Celery Worker):
```bash
celery -A rotra_logistics worker -l info
```

Terminal 2 (Celery Beat - Scheduler):
```bash
celery -A rotra_logistics beat -l info
```

Now the task will automatically run daily at 2 AM!

---

## Monitoring

### Check what's scheduled
```bash
# View all Celery tasks
celery -A rotra_logistics inspect active

# View scheduled tasks
celery -A rotra_logistics inspect scheduled
```

### View logs
The terminal running Celery Beat/Worker will show:
```
[2026-02-20 02:00:00] Task delete_old_unassigned_loads scheduled
[2026-02-20 02:00:01] Task executing: delete_old_unassigned_loads...
[2026-02-20 02:00:05] Task completed successfully
```

---

## Customization

### Change deletion criteria in Load model

Edit `logistics_app/models.py` - Load class, add a custom manager:

```python
class Load(models.Model):
    # ... existing code ...
    
    class LoadManager(models.Manager):
        def unassigned_old(self, days=2):
            from django.utils import timezone
            from datetime import timedelta
            
            cutoff = timezone.now() - timedelta(days=days)
            return self.filter(driver__isnull=True, created_at__lt=cutoff)
    
    objects = LoadManager()
```

Then use:
```python
old_unassigned = Load.objects.unassigned_old(days=2)
```

### Change notification before deletion

Modify the management command to send email/notification before deleting:

```python
# In delete_unassigned_loads.py, before deleting:
for load in unassigned_loads:
    # Send email to admin
    send_mail(
        f'Auto-deleting unassigned load {load.load_id}',
        f'Load will be deleted: {load.load_id}',
        'noreply@rotra.com',
        ['admin@rotra.com'],
    )
```

---

## Testing

### Test the management command:
```bash
# Dry run (no deletion, just preview)
python manage.py delete_unassigned_loads --dry-run

# Test deletion with a custom date range
python manage.py delete_unassigned_loads --days 1  # Delete loads > 1 day old
```

### Test Celery task manually:
```bash
python manage.py shell

# In shell:
from logistics_app.tasks import delete_old_unassigned_loads
delete_old_unassigned_loads.delay(2)  # Run task asynchronously
```

---

## Troubleshooting

**Problem:** "No such file or directory" when running cron
- **Solution:** Use absolute paths in crontab. Get path with `which python`

**Problem:** Celery task not running
- **Solution:** Check that both Worker and Beat are running in separate terminals

**Problem:** "celery command not found"
- **Solution:** Install Celery: `pip install celery`

**Problem:** Redis connection error
- **Solution:** Install Redis: `sudo apt install redis-server` (Linux) or use `docker run redis`

---

## Summary

| Method | Setup Time | Automation | Recommended |
|--------|-----------|-----------|-------------|
| Manual | 5 mins | No | Dev/Testing |
| Cron | 10 mins | Yes | Production (simple) |
| Celery | 30 mins | Yes | Production (robust) |

Choose based on your needs. For most deployments, **Cron + Management Command** is the simplest and most reliable.
