from django.db import models


class CronSettings(models.Model):
    title = models.CharField(max_length=75)
    min = models.CharField(max_length=5, default="*", help_text='min: 0-59')
    hour = models.CharField(max_length=5, default="*", help_text='hour: 0-23')
    day_of_month = models.CharField(max_length=10, default="*", help_text='day of month: 1-31')
    month = models.CharField(max_length=10, default="*", help_text='month: 1-12')
    day_of_week = models.CharField(max_length=10, default="*", help_text='day of week: 0-6, Sunday=0')

    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('title',)
        verbose_name_plural = 'Cron settings'

    def __unicode__(self):
        return u'%s' % (self.title)

    def crontab_settings(self):
        """
        defines the crontab settings based on the chosen options
        """
        return '%s %s %s %s %s' % (
            self.min, self.hour, self.day_of_month,
            self.month, self.day_of_week
        )
