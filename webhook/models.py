from django.db import models


class WebhookLog(models.Model):
    STATUS_CHOICES = [
        ('pending', 'В обработке'),
        ('success', 'Успешно'),
        ('error', 'Ошибка'),
    ]

    PIPELINE_CHOICES = [
        ('default', 'Основная'),
        ('klaster', 'Кластер'),
    ]

    payload = models.JSONField(verbose_name='Данные вебхука')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    pipeline = models.CharField(max_length=20, choices=PIPELINE_CHOICES, default='default', verbose_name='Воронка')
    error_message = models.TextField(blank=True, null=True)
    amocrm_contact_id = models.IntegerField(blank=True, null=True)
    amocrm_lead_id = models.IntegerField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = 'Лог вебхука'
        verbose_name_plural = 'Логи вебхуков'
        ordering = ['-created_at']

    def __str__(self):
        return f"Webhook {self.id} ({self.get_pipeline_display()}) - {self.status}"