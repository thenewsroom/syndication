# -*- coding: utf-8 -*-
from __future__ import unicode_literals

# Create your models here.
import urllib

from django.db import models
from django.conf import settings
from utils.cutils import (TAG_LIST, TAG_ATTRS)
from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy as _
from django.template.defaultfilters import slugify
# from django.forms import ValidationError
from datetime import datetime

# Create your models here.

FREQUENCY = (("YEARLY", _("Yearly")),
             ("MONTHLY", _("Monthly")),
             ("WEEKLY", _("Weekly")),
             ("DAILY", _("Daily")),
             ("HOURLY", _("Hourly")),
             ("MINUTELY", _("Minutely")),
             ("SECONDLY", _("Secondly"))
             )

STATUS = ((0, "D"),
          (1, "U"),
          )

TAG_CHOICES = tuple([(item, item) for item in TAG_LIST])
TAG_ATTRS_CHOICES = tuple([(item, item) for item in TAG_ATTRS])
ACCOUNT_TYPE = (('EX', 'External'), ('IN', 'Internal'))

URL_STATUS = (
    ('U', 'Updated'),
    ('NU', 'Not Updated'),
)

SOURCE_STATUS = (
    ('I', 'Is Running'),
    ('C', 'Complete'),
)


class SourceAccount(models.Model):
    name = models.CharField(max_length=250)
    slug = models.SlugField(max_length=300, unique=True)
    url_to_update = models.CharField(max_length=800, blank=True, null=True)
    account_type = models.CharField(max_length=2, choices=ACCOUNT_TYPE, default="IN")
    notify_to = models.ManyToManyField(User, blank=True)

    def __unicode__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super(SourceAccount, self).save()


SOURCE_ADMIN_URL = "/admin/websource/sourceurl/"


class Source(models.Model):
    account = models.ForeignKey(SourceAccount)
    name = models.CharField(max_length=250)
    slug = models.SlugField(max_length=500, unique=True)
    sid = models.CharField(max_length=200, blank=True, null=True)
    frequency = models.CharField(choices=FREQUENCY, max_length=10, default='DAILY')
    subscribe_to_emails = models.BooleanField(default=False)
    created_on = models.DateTimeField()
    updated_on = models.DateTimeField()
    is_integrated = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    exclude_tag = models.CharField(max_length=100, choices=TAG_CHOICES, blank=True, null=True,
                                   help_text="Tag that we need to exclude from each URL of this source")
    exclude_tag_attr = models.CharField(max_length=100, choices=TAG_ATTRS_CHOICES, null=True, blank=True)
    exclude_tag_attr_value = models.CharField(max_length=800, null=True, blank=True)
    assigned_to = models.ForeignKey(User, default=8)

    class Meta:
        ordering = ('name',)

    def __unicode__(self):
        return self.name

    def _get_params(self, filter_by, value=True):
        params = {}
        params[filter_by] = '0' if not value else '1'
        params['source__account__id__exact'] = self.account.id
        params['source__id__exact'] = self.id
        return urllib.urlencode(params)

    def url_count(self):
        '''
        get the count of the occurence of the given entity
        across all stories
        '''
        return self.sourceurl_set.only('id').count()

    def need_triage(self):
        count = self.sourceurl_set.filter(need_triage=True).count()
        params = self._get_params("need_triage")
        return '''<b><a href="%(SOURCE_ADMIN_URL)s?%(params)s">
                %(count)s
                </a></b>''' % {'SOURCE_ADMIN_URL': SOURCE_ADMIN_URL,
                               'params': params, 'count': count
                               }

    def get_manual_triage(self):
        """
        returns count of manual triaged urls
        """
        count_urls = self.sourceurl_set.filter(manual_triage=True).count()
        return count_urls

    def get_doc_count(self):
        """
        returns count of updated urls
        """
        suqs = self.sourceurl_set.only('url', 'is_updated').filter(is_updated=True)
        return suqs.count()

    def get_nodoc_count(self):
        """
        returns count of urls not updated
        """
        suqs = self.sourceurl_set.only('url', 'is_updated').filter(is_updated=False)
        return suqs.count()

    def get_to_do_count(self):
        """
        returns count of URLs updated but not checked by user
        """
        return self.sourceurl_set.only("id", "is_updated", "is_checked",
                                       ).filter(is_updated=True, is_checked=False).count()

    def docs(self):
        """
        returns a custom string with count for source admin
        """
        count_url = self.get_doc_count()
        params = self._get_params("is_updated__exact")
        return '''<b><a href="%(SOURCE_ADMIN_URL)s?%(params)s">
                %(count)s
                </a></b>''' % {'SOURCE_ADMIN_URL': SOURCE_ADMIN_URL,
                               'params': params,
                               'count': count_url
                               }

    def nodocs(self):
        """
        returns a custom string with count for source admin
        """
        count_url = self.get_nodoc_count()
        params = self._get_params("is_updated__exact", value=False)
        return '''<b><a href="%(SOURCE_ADMIN_URL)s?%(params)s">
                %(count)s
                </a></b>''' % {'SOURCE_ADMIN_URL': SOURCE_ADMIN_URL,
                               'params': params,
                               'count': count_url
                               }

    def total_url(self):
        """
        returns a custom string with total url count.
        """
        return "<b><a href='%s?source__id__exact=%d'>%d</a></b>" % (
            SOURCE_ADMIN_URL, self.id, self.url_count())

    def to_do(self):
        """
        get all URL count filter by updated True and checked False
        """
        return "<b><a href='%s?source__id__exact=%d&is_updated__exact=1&is_checked__exact=0'>%d</a></b>" % (
            SOURCE_ADMIN_URL, self.id, self.get_to_do_count())

    def manual_triage(self):
        return "<b><a href='%s?source__id__exact=%d&manual_triage=1'>%d</a></b>" % (
            SOURCE_ADMIN_URL, self.id, self.get_manual_triage())


    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        if not self.created_on:
            self.created_on = datetime.now()
        self.updated_on = datetime.now()
        super(Source, self).save()

    nodocs.allow_tags = True
    docs.allow_tags = True
    need_triage.allow_tags = True
    total_url.allow_tags = True
    to_do.allow_tags = True
    manual_triage.allow_tags = True


class SourceUrl(models.Model):
    name = models.CharField(max_length=250, blank=True, null=True)
    source = models.ForeignKey(Source)
    url = models.URLField(max_length=500)
    uid = models.CharField(max_length=200, blank=True, null=True)
    tag_name = models.CharField(max_length=100, choices=TAG_CHOICES, blank=True, null=True)
    tag_attr = models.CharField(max_length=100, choices=TAG_ATTRS_CHOICES, null=True, blank=True)
    tag_attr_value = models.CharField(max_length=800, null=True, blank=True)
    old_snapshot = models.TextField(blank=True)
    new_snapshot = models.TextField(blank=True)
    overwrite = models.BooleanField(default=False)
    is_updated = models.BooleanField(default=False)
    need_triage = models.BooleanField(default=True)
    is_working = models.BooleanField(default=True)
    created_on = models.DateTimeField()
    tag_updated_on = models.DateTimeField()
    last_triaged = models.DateTimeField(blank=True)
    created_by = models.ForeignKey(User, default=8, related_name='created_sourceurls')
    updated_by = models.ForeignKey(User, blank=True, null=True, related_name='updated_sourceurls')
    is_checked = models.BooleanField(default=True)
    last_checked = models.DateTimeField(blank=True)
    response_code = models.CharField(max_length=10, default='200')
    response_msg = models.CharField(max_length=400, default='OK')
    doc_counter = models.IntegerField(default=0)
    nodoc_counter = models.IntegerField(default=0)
    last_doc_found_on = models.DateTimeField()
    status = models.IntegerField(choices=STATUS, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    specific_rule = models.TextField(null=True, blank=True)
    scraping_rules = models.ManyToManyField('story.ScrapingRule', blank=True)
    published_story_count = models.IntegerField(default=0)
    manual_triage = models.BooleanField(default=False)

    class Meta:
        ordering = ('is_checked',)

    def __unicode__(self):
        if self.source.account.id == 1:
            return self.uid
        else:
            return self.name

    def get_remarks(self):
        """
        merge common remarks and specefic remarks and prepare story remark.
        """
        storyRemark = u""
        if self.specific_rule and self.specific_rule.strip():
            storyRemark += u"%s\n" % (self.specific_rule.encode('utf-8').strip())
        storyRemark += u"\n".join([sr.rule.encode('utf-8') for sr in self.scraping_rules.all()])
        return storyRemark

    def aid_link(self):
        """
        returns a custom string with count for source admin
        """
        params = {'domain': self.source.id, 'source': self.id,
                  'body_text': self.get_leadline_and_source().encode('utf-8'),
                  'rule_box': self.get_remarks().encode('utf-8'),
                  }
        paramsEncode = urllib.urlencode(params)
        return '''<b><a href="%s" onclick="return popitup('%s', '/admin/story/story/add/?%s')">%s</a></b>''' % (
            self.url, self.url, paramsEncode, self.uid)

    def published_count(self):
        """
        """
        return '''<b><a href="/admin/story/story/?status__exact=2&source__id=%s" target="_blank">%s</a></b>''' % (
        self.id, self.published_story_count)

    published_count.allow_tags = True
    aid_link.allow_tags = True
    aid_link.admin_order_field = 'uid'
    published_count.admin_order_field = 'published_story_count'

    def save(self, *args, **kwargs):
        if self.source:
            self.uid = self.uid.strip()
            self.name = self.name.strip()

        if not self.created_on:
            self.created_on = datetime.now()

        if not self.tag_updated_on:
            self.tag_updated_on = datetime.now()

        if self.pk is not None:
            new_snapshot = kwargs.get('new_snapshot', self.new_snapshot)
            if new_snapshot:
                if self.overwrite:
                    self.old_snapshot = self.new_snapshot
                    self.new_snapshot = new_snapshot
                    self.overwrite = False
                    if self.old_snapshot != self.new_snapshot:
                        self.is_updated = True
                        self.doc_counter += 1
                        self.nodoc_counter = 0
                        self.last_doc_found_on = datetime.now()
                    else:
                        self.is_updated = False
                self.need_triage = False
            else:
                self.need_triage = True

            if not self.tag_name:
                self.need_triage = True

            changed = False
            fields = ["tag_name", "tag_attr", "tag_attr_value"]
            # check if only tag details changed
            # for field in self._meta.get_all_field_names():
            for field in fields:
                old_value = getattr(
                    self.__class__._default_manager.get(id=self.id), field
                )
                new_value = getattr(self, field)
                if new_value != old_value:
                    changed = True
                    break
            if changed:
                self.tag_updated_on = datetime.now()
            if self.is_checked is True:
                self.last_checked = datetime.now()

        super(SourceUrl, self).save()


class SourceUrlStatus(models.Model):
    sourceurl = models.ForeignKey(SourceUrl)
    comment = models.TextField()
    status = models.CharField(max_length=2, choices=URL_STATUS)
    created_on = models.DateTimeField()
    patent_url = models.CharField(max_length=1000, null=True, blank=True)

    class Meta:
        verbose_name_plural = 'Status - URL Update'

    def __unicode__(self):
        return u"%s: %s" % (self.sourceurl.url, self.status)

    def _source(self):
        return self.sourceurl.source.name

    _source.allow_tags = True

    def save(self, *args, **kwargs):
        if not self.created_on:
            self.created_on = datetime.now()
        super(SourceUrlStatus, self).save()


class SourceStatus(models.Model):
    source = models.ForeignKey(Source)
    status = models.CharField(max_length=2, choices=SOURCE_STATUS)
    created_on = models.DateTimeField()

    class Meta:
        verbose_name_plural = 'Status - Source Update'

    def __unicode__(self):
        return "%s: %s" % (self.source.name, self.status)

    def _sid(self):
        if self.source.sid:
            return self.source.sid
        return self.source.id

    def save(self, *args, **kwargs):
        if not self.created_on:
            self.created_on = datetime.now()
        super(SourceStatus, self).save()
