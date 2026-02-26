"""
Celery periodic tasks for automated load management
"""
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from logistics_app.models import Load


@shared_task(bind=True)
def delete_old_unassigned_loads(self, days=1):
    """
    Periodic task to delete loads with no driver assigned after N days.
    
    Schedule this to run daily:
    - Add to CELERY_BEAT_SCHEDULE in settings.py
    
    Example:
        'delete-old-unassigned-loads': {
            'task': 'logistics_app.tasks.delete_old_unassigned_loads',
            'schedule': crontab(hour=2, minute=0),  # Run at 2 AM daily
        },
    """
    try:
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Find unassigned loads older than N days
        unassigned_loads = Load.objects.filter(
            driver__isnull=True,
            created_at__lt=cutoff_date
        )
        
        count = unassigned_loads.count()
        
        if count == 0:
            return {
                'status': 'success',
                'message': f'No unassigned loads found older than {days} days',
                'deleted_count': 0
            }
        
        # Delete the loads
        deleted_count, _ = unassigned_loads.delete()
        
        return {
            'status': 'success',
            'message': f'Deleted {deleted_count} unassigned load(s)',
            'deleted_count': deleted_count
        }
    
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Error deleting loads: {str(e)}',
            'deleted_count': 0
        }
