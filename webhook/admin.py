from django.contrib import admin
from .models import WebhookLog


@admin.register(WebhookLog)
class WebhookLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'status', 'amocrm_contact_id', 'amocrm_lead_id', 'created_at', 'processed_at']
    list_filter = ['status', 'created_at']
    search_fields = ['amocrm_contact_id', 'amocrm_lead_id', 'error_message']
    readonly_fields = ['created_at', 'processed_at']

    fieldsets = (
        ('Основная информация', {
            'fields': ('status', 'created_at', 'processed_at')
        }),
        ('AmoCRM IDs', {
            'fields': ('amocrm_contact_id', 'amocrm_lead_id')
        }),
        ('Данные вебхука', {
            'fields': ('payload', 'error_message'),
            'classes': ('collapse',)
        }),
    )