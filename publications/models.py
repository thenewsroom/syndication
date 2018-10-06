import re
import os
# import time
# import copy
from datetime import datetime

# django
from django.conf import settings
from django.db import models

from accounts.models import Account
# from cutils.models import CronSettings
# from cutils.utils import BUYER_SHORT_NAME_MAP
# from mptt.models import MPTTModel


LOAD_STATUS = (
    ('I', 'In Progress'),
    ('C', 'Complete'),
)

FILE_LOAD_STATUS = (
    ('A', 'Agency'),
    ('P', 'Pending'),
    ('S', 'Success'),
    ('R', 'Reject'),
    ('D', 'Duplicate'),
)

FEED_LOADER_TYPE = (
    ("M", "Manual"),
    ("A", "Auto"),
    ("W", "WIP"),
)

PUBLICATION_STATUS_CHOICES = (
    (-1, 'Denied'),
    (0, 'Not yet proposed'),
    (1, 'Proposed'),
    (2, 'Lived'),
)


class FeedFormat(models.Model):
    feed_type = models.CharField(max_length=30)
    auto_manual = models.CharField(max_length=1, choices=FEED_LOADER_TYPE)

    class Meta:
        ordering = ('auto_manual',)

    def __unicode__(self):
        return u'%s::%s' % (self.auto_manual, self.feed_type)


class Publication(models.Model):
    title = models.CharField(max_length=75)
    slug = models.SlugField(max_length=75)
    description = models.CharField(max_length=255, null=True, blank=True)
    account = models.ForeignKey(Account, limit_choices_to={'type': 'P'})
    # category = models.ManyToManyField(Category, blank=True)
    time_zone = models.CharField(max_length=3, default="GMT")
    #load_frequency = models.ForeignKey(CronSettings)
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)
    copyright = models.CharField(max_length=255, null=True, blank=True,
                                 help_text="Leave blank to pick the default account level settings, \
                                 for Custom say: Custom Copyright for issued by")
    feed_format = models.ForeignKey(FeedFormat, null=True, blank=True)
    auto_schedule = models.BooleanField(default=False)
    #extract_entities = models.BooleanField(default=False)
    disclaimer = models.TextField(null=True, blank=True,
                                  help_text="Any text added here will be suffixed \
                                  to each and every Entry of this publication")
    #tag_industry = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    #archive_day_range = models.IntegerField(default=30)

    class Meta:
        ordering = ('title',)
        unique_together = (('slug', 'account'))

    def __unicode__(self):
        return u'%s' % (self.title)


class RichFeed(models.Model):
    title = models.CharField('Section', max_length=100, blank=True)
    publication = models.ForeignKey(Publication)
    rss_url = models.URLField(max_length=255)
    web_url = models.URLField(null=True, blank=True,  max_length=800)
    ttl = models.IntegerField(default=300)
    active = models.BooleanField(default=True)

    # class Meta:
    #     ordering = ('title',)

    def __unicode__(self):
        return u'%s' % (self.title)

    def _rss_url(self):
        return '<a href="%s" target="_blank">rss url</a>' % (self.rss_url)

    _rss_url.allow_tags = True

    def _web_url(self):
        return '<a href="%s" target="_blank">web url</a>' % (self.web_url)

    _web_url.allow_tags = True

def remove_html_tags(data):
    p = re.compile(r'<.*?>')
    return p.sub('', data)

class FeedLoadStatus(models.Model):
    filename = models.CharField(max_length=255)
    publication = models.ForeignKey(Publication)
    status = models.CharField(max_length=1, choices=FILE_LOAD_STATUS, default='P')
    comments = models.TextField(null=True)
    created_on = models.DateTimeField(auto_now_add=True)

    # class Meta:
    #     verbose_name_plural = 'Status - File Load'

    def __unicode__(self):
        return "%s" % (self.filename)

class PublicationLoadStatus(models.Model):
    title = models.CharField(max_length=85, null=True)
    publication = models.ForeignKey(Publication)
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True)
    expected_count = models.IntegerField(default=-1)
    load_count = models.IntegerField(default=0)
    reject_count = models.IntegerField(default=0)
    load_status = models.CharField(max_length=1, choices=LOAD_STATUS, default="I")
    load_date = models.DateField(auto_now_add=True)
    created_on = models.DateTimeField(auto_now_add=True)
    notify_publisher = models.BooleanField(default=False)
    comments = models.TextField(null=True)

    class Meta:
        ordering = ('-created_on',)
        get_latest_by = 'created_on'
        # verbose_name_plural = 'Status - Publication Load'

    def __unicode__(self):
        if self.title:
            return u'%s' % (self.title)
        else:
            return (self.load_date).strftime("%Y-%m-%d")

    def is_active(self):
        """
        checks if a load is active / in progress for the given publication
        """
        if self.load_status == "I":
            return True
        return False

    # def save(self):
    #     if not self.title:
    #         self.title = u'{}-{}'.format(
    #             self.publication.slug, datetime.now().strftime("%Y%m%d")
    #         )
    #     if self.expected_count == -1:
    #         self.expected_count = (self.publication).expected_files
    #     if self.load_status == 'C':
    #         self.end_time = datetime.now()
    #
    #     super(PublicationLoadStatus, self).save()
    #
    #     # No matter what notify ops team as per requirement in case of Indian Express
    #     indian_express_account_id = 1
    #     if self.comments or self.publication.account.id == indian_express_account_id:
    #         self.send_status_mail()


    def send_status_mail(self):
        """
        sends an email to the delivery list
        TODO add options to add multiple users to the list
        """
        from django.core.mail import send_mail
        subject = "App Load Status | %s - %s | S%02d/-R%02d" % (
            self.publication.account, self.title, self.load_count, self.reject_count)
        body = "Account: %s\nPublication: %s\nStatus: %s\nTime:%s - %s\nLoaded: %02d\nRejected: %02d\n\nComments\n:%s\n" % (
            self.publication.account, self.publication, self.load_status, self.start_time, self.end_time, self.load_count, self.reject_count, self.comments)
        body = body + settings.EMAIL_DEFAULT_SIGNATURE
        if self.publication.id in [2,3,60,61,62,63,370,39]:
            return send_mail(subject, body, settings.DEFAULT_FROM_EMAIL,
                [settings.ADMIN_EMAIL, 'anand.kumar@contify.com', 'rajesh.swain@contify.com', 'tapan.puhan@contify.com'], fail_silently=True)
        else:
            return send_mail(subject, body, settings.DEFAULT_FROM_EMAIL,
                [settings.ADMIN_EMAIL], fail_silently=True)

class FeedScreenshot(models.Model):
    title = models.CharField(max_length=350)
    rss_feed = models.ForeignKey(RichFeed)
    created_on = models.DateTimeField('Created on', auto_now_add=True, db_index=True)

    def __unicode__(self):
        return u'%s : %s' % (self.rss_feed.rss_url, self.title)

class PublicationStatus(models.Model):

    class Meta:
        verbose_name_plural = "Publication Status"

    LIVED = 2
    PROPOSED = 1
    NOT_YET_PROPOSED = 0
    DENIED = -1

    publication = models.ForeignKey(Publication)
    client = models.ForeignKey(Account, limit_choices_to={'type': 'B'},
                               null=True, blank=True)
    status = models.IntegerField(choices=PUBLICATION_STATUS_CHOICES, default=0)

    def __unicode__(self):
        return u"%s, %s, %d" % (self.publication.title, self.client, self.status)

