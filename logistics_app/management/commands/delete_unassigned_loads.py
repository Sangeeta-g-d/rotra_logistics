from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from logistics_app.models import Load


class Command(BaseCommand):
    help = 'Delete loads that have no driver assigned and are older than 2 days'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=2,
            help='Number of days to wait before deleting unassigned loads (default: 2)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        
        # Calculate the cutoff date (2 days ago)
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Find all loads with:
        # 1. No driver assigned (driver is NULL)
        # 2. Created before the cutoff date
        unassigned_loads = Load.objects.filter(
            driver__isnull=True,
            created_at__lt=cutoff_date
        ).select_related('customer')
        
        count = unassigned_loads.count()
        
        if count == 0:
            self.stdout.write(
                self.style.SUCCESS('✓ No unassigned loads older than {} days found.'.format(days))
            )
            return
        
        # Display the loads that will be deleted
        self.stdout.write(
            self.style.WARNING(f'\n⚠ Found {count} unassigned load(s) created before {cutoff_date}:')
        )
        self.stdout.write('-' * 80)
        
        for load in unassigned_loads:
            age_days = (timezone.now() - load.created_at).days
            self.stdout.write(
                f'  • Load ID: {load.load_id} | Customer: {load.customer.customer_name} | '
                f'Created: {load.created_at.strftime("%Y-%m-%d %H:%M:%S")} | Age: {age_days} days'
            )
        
        self.stdout.write('-' * 80)
        
        if dry_run:
            self.stdout.write(
                self.style.NOTICE(f'\n[DRY RUN] Would delete {count} load(s). Use without --dry-run to actually delete.')
            )
            return
        
        # Ask for confirmation
        confirm = input(f'\nAre you sure you want to delete {count} load(s)? (yes/no): ')
        
        if confirm.lower() != 'yes':
            self.stdout.write(self.style.WARNING('✗ Deletion cancelled.'))
            return
        
        # Delete the loads
        deleted_count, _ = unassigned_loads.delete()
        
        self.stdout.write(
            self.style.SUCCESS(f'\n✓ Successfully deleted {deleted_count} unassigned load(s)!')
        )
