from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, HoldingCharge

class CustomUserAdmin(UserAdmin):
    model = CustomUser
    fieldsets = UserAdmin.fieldsets + (
        ('Additional Info', {
            'fields': ('address', 'phone_number', 'pan_number', 'profile_image'),
        }),
    )

class HoldingChargeAdmin(admin.ModelAdmin):
    list_display = ('id', 'load', 'amount', 'trip_stage', 'added_by', 'created_at')
    list_filter = ('trip_stage', 'created_at', 'load')
    search_fields = ('load__load_id', 'reason', 'added_by__full_name')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Load Information', {
            'fields': ('load',)
        }),
        ('Charge Details', {
            'fields': ('amount', 'trip_stage', 'reason')
        }),
        ('Metadata', {
            'fields': ('added_by', 'created_at', 'updated_at')
        }),
    )

admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(HoldingCharge, HoldingChargeAdmin)

