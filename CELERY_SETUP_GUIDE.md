# Celery Setup and Quick Start Guide

## Prerequisites

### 1. Install Required Packages

```bash
pip install celery redis
```

Or if you prefer RabbitMQ instead of Redis:
```bash
pip install celery
# RabbitMQ will need to be installed separately on your system
```

### 2. Install Redis (Message Broker)

#### On Linux (Ubuntu/Debian):
```bash
sudo apt-get install redis-serveru
sudo systemctl start redis-server
```

#### On macOS (with Homebrew):
```bash
brew install redis
brew services start redis
```

#### On Windows (using Docker - Recommended):
```bash
docker run -d -p 6379:6379 redis:latest
```

#### Or install Redis directly on Windows:
Download from: https://github.com/microsoftarchive/redis/releases

---

## Running Celery

You need TWO terminal windows running simultaneously:

### Terminal 1: Start Celery Worker
```bash
cd c:\Users\admin\OneDrive\Documents\Desktop\CT\rotra_logistics
celery -A rotra_logistics worker -l info
```

**Output should look like:**
```
celery@HOSTNAME v5.3.x
[config]
.
.
[pool: prefork] >> max concurrency: 4
 -------------- celery@HOSTNAME v5.x.x
--- ***** -----
-- ******* ----
- *** --- * ---
- ** ---------- [queues]
 .              .celery.pidbox
                .celery
         -------------- [tasks]
                    .debug_task
                    .logistics_app.tasks.delete_old_unassigned_loads
```

### Terminal 2: Start Celery Beat (Task Scheduler)
```bash
cd c:\Users\admin\OneDrive\Documents\Desktop\CT\rotra_logistics
celery -A rotra_logistics beat -l info
```

**Output should look like:**
```
celery beat v5.3.x is starting.
[config]
.
.
LocalTime 2026-02-20 02:00:00+00:00
Configuration:
    -> app.conf.timezone = 'UTC'
    -> app.conf.enable_utc = True

[2026-02-20 02:00:00,123] INFO/MainProcess [beat] Scheduler: Sent due task 'delete-old-unassigned-loads' (logistics_app.tasks.delete_old_unassigned_loads)
```

---

## Testing Celery

### Test 1: Check if Worker is Running
```bash
celery -A rotra_logistics inspect active
```

Should return:
```
{'celery@HOSTNAME': {'active': []}}
```

### Test 2: Run the Task Manually
```bash
# Open Django shell
python manage.py shell

# In the shell:
from logistics_app.tasks import delete_old_unassigned_loads
delete_old_unassigned_loads.delay(2)  # Returns a task ID
```

### Test 3: View Scheduled Tasks
```bash
celery -A rotra_logistics inspect scheduled
```

---

## Verify Configuration

Check that Celery is properly configured:

```bash
python manage.py shell

# In shell:
from django.conf import settings
print("Broker URL:", settings.CELERY_BROKER_URL)
print("Result Backend:", settings.CELERY_RESULT_BACKEND)
print("Beat Schedule:", settings.CELERY_BEAT_SCHEDULE)
```

---

## Production Setup (Using Supervisor)

For production, use Supervisor to manage Celery processes:

### 1. Install Supervisor
```bash
sudo apt install supervisor
```

### 2. Create Config Files

Create `/etc/supervisor/conf.d/celery-worker.conf`:
```ini
[program:celery-worker]
process_name=%(program_name)s_%(process_num)02d
command=celery -A rotra_logistics worker -l info
autostart=true
autorestart=true
numprocs=1
directory=/path/to/rotra_logistics
user=www-data
redirect_stderr=true
stdout_logfile=/var/log/celery-worker.log
```

Create `/etc/supervisor/conf.d/celery-beat.conf`:
```ini
[program:celery-beat]
process_name=%(program_name)s
command=celery -A rotra_logistics beat -l info
autostart=true
autorestart=true
directory=/path/to/rotra_logistics
user=www-data
redirect_stderr=true
stdout_logfile=/var/log/celery-beat.log
```

### 3. Start Services
```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start celery-worker
sudo supervisorctl start celery-beat
```

---

## Troubleshooting

### Issue: "No module named 'celery'"
**Solution:** Install Celery
```bash
pip install celery redis
```

### Issue: Redis connection error
**Solution:** Make sure Redis is running
```bash
# Check if Redis is running
redis-cli ping  # Should return "PONG"

# Start Redis if not running
redis-server  # Unix/Mac
# or via Docker:
docker run -d -p 6379:6379 redis:latest
```

### Issue: Tasks not executing
**Check:**
1. Both Worker and Beat terminals are running
2. No errors in the terminal output
3. Run: `celery -A rotra_logistics inspect active` to verify

### Issue: "ModuleNotFoundError: No module named 'rotra_logistics'"
**Solution:** Make sure you're in the correct directory
```bash
cd /path/to/rotra_logistics
celery -A rotra_logistics worker -l info
```

---

## Environment Variables (Optional)

Add to your `.env` file:
```
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

---

## Monitoring Celery Tasks

### Using Flower (Web Dashboard)

1. Install Flower:
```bash
pip install flower
```

2. Run Flower:
```bash
celery -A rotra_logistics flower
```

3. Open in browser: `http://localhost:5555`

---

## Summary

✅ **Files Created/Modified:**
- `rotra_logistics/celery.py` - Celery app initialization
- `rotra_logistics/__init__.py` - Celery app import
- `rotra_logistics/settings.py` - Celery configuration
- `logistics_app/tasks.py` - Task definitions

✅ **To Start Celery:**
1. Terminal 1: `celery -A rotra_logistics worker -l info`
2. Terminal 2: `celery -A rotra_logistics beat -l info`

✅ **Your scheduled task runs daily at 2:00 AM UTC** - deletes unassigned loads older than 2 days!

**Next Steps:**
- Start both Celery processes
- Monitor the logs to confirm task execution
- Optionally install Flower for a web dashboard
- For production, set up Supervisor to manage processes
