import re
import sys
from datetime import datetime, timedelta

# core django imports
from django.conf import settings
from django.db import models
from django.template.defaultfilters import slugify
from django.template.defaultfilters import  striptags
from django.contrib.auth.models import User

from accounts.models import Account
from publications.models import Publication, RichFeed
from cutils.utils import (
    pre_process_data, truncate, unicode_to_ascii
)


PUB_STATUS = (
    (-1, 'Rejected'),
    (0, 'Draft'),
    (1, 'Pending Review'),
    (2, 'Published'),
)

STATUS_REASON = (
    (0, 'None'),
    (1, 'Tag fetch failed'),
    (2, 'Word Count'),
    (3, 'Duplicate'),
    (4, 'Merged Words'),
)

class MergedWord(models.Model):
    """
    stores merged words. Which are used to check and validate entry body data.
    """
    name = models.CharField(max_length=250, db_index=True)
    created_on = models.DateTimeField()
    created_by = models.ForeignKey(User, default=1)

    def __unicode__(self):
        return u'%s' %(self.name)

    def save(self, *args, **kwargs):
        """
        to set default values of created on.
        """
        if not self.created_on:
            self.created_on = datetime.now()

        super(MergedWord, self).save(*args, **kwargs)

class Industry(models.Model):
    """
    class to manage the Industry relationships
    Every object has a code and a parent
    """
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=255)
    parent = models.ForeignKey(
            'self', blank=True, null=True, related_name='child_set'
    )

    class Meta:
        ordering = ['code',]
        verbose_name_plural = 'Industries'

    def __unicode__(self):
        return u'%s' % (self.full_name())

    def level(self):
        """
        count the number of parents
        """
        if not self.parent:
            return 0
        return 1 + self.parent.level()

    def full_name(self):
        if self.parent_id:
            return '%s%s%s' %(self.parent, self.get_separator(), self.name)
        else:
            return self.name

    def get_separator(self):
        return ' :: '

    def is_leaf(self):
        """
        returns True if this entity does not have a child
        """
        if self.child_set.all():
            return False
        return True
class Category(models.Model):
    text = models.CharField(max_length=75)
    slug = models.CharField(max_length=75)

    def __unicode__(self):
        return self.text

    class Meta:
        verbose_name_plural = "categories"

    def get_absolute_url(self):
        return "/category/%s/" %(self.slug)

    def set_slug(self):
        """
        Auto-populate an empty slug field from the Entry title
        """
        if not self.slug:
            # Where self.name is the field used for 'pre-populate from'
            self.slug = slugify(self.text)


class Entry(models.Model):
    title = models.CharField('Headline', max_length=400)
    sub_headline = models.CharField(
        'Secondary headline (optional)', max_length=255, blank=True
    )
    slug = models.SlugField(
        max_length=350,
        # unique_for_date='pub_date',
        help_text='Automatically built from the title.'
    )
    body_html = models.TextField(blank=True)
    excerpt = models.TextField(blank=True)
    by_line = models.CharField(max_length=200, blank=True)
    pub_date = models.DateTimeField('Date published', db_index=True)

    keywords = models.CharField(max_length=255, blank=True)
    sites_tag = models.CharField(max_length=255, blank=True, null=True)
    publication = models.ForeignKey(
        Publication, limit_choices_to={'active': True}
    )
    status = models.IntegerField(choices=PUB_STATUS, default=0)

    date_line = models.CharField(max_length=255, blank=True)
    credit_line = models.CharField(
        max_length=255, blank=True,
        help_text="Leave it blank for it to be populated by the system."
    )
    tag_line = models.CharField(max_length=255, blank=True)

    updated_on = models.DateTimeField(auto_now=True)
    created_on = models.DateTimeField(
        'Created on', auto_now_add=True, db_index=True
    )
    status_reason = models.IntegerField(
        choices=STATUS_REASON, default=0
    )
    created_by = models.ForeignKey(
        User, limit_choices_to={'is_staff': True, 'is_active': True},
        related_name='entries', default=1
    )
    industry = models.ForeignKey(Industry, blank=True, null=True)
    published_by = models.ForeignKey(
        User, limit_choices_to={'is_staff': True, 'is_active': True},
        related_name='Entries', blank=True, null=True
    )
    cpr = models.BooleanField('Corporate Press Release', default=False)
    gpr = models.BooleanField('Government Press Release', default=False)
    business_news = models.BooleanField('Business News', default=False)
    url = models.URLField(
        max_length=800, blank=True, db_index=True
    )
    volume_no = models.IntegerField(blank=True, null=True)
    issue_no = models.IntegerField(blank=True, null=True)
    author = models.CharField(max_length=200, blank=True)
    is_scheduled = models.BooleanField("Send To Securities", default=False)
    industry_rejected_news = models.BooleanField(default=False)
    #send_to_factiva = models.BooleanField(default=False)
    translated_content = models.BooleanField(default=False)
    approved_on = models.DateTimeField(blank=True, null=True, db_index=True)
    approved_by = models.ForeignKey(
        User, limit_choices_to={'is_staff': True, 'is_active': True},
        related_name='approved_entries', blank=True, null=True
    )
    rich_feed = models.ForeignKey(RichFeed, blank=True, null=True)
    comments = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'cms_entry_master'
        ordering = ('-pub_date',)
        get_latest_by = 'pub_date'
        verbose_name_plural = 'Contents'
        unique_together = (('title', 'by_line', 'publication', 'pub_date'),)

        permissions = (
            ("can_view", "Can view"),
            ("can_change_entry_all", "Can change all entries"),
            ("can_publish", "Can publish entries"),
        )

    def __unicode__(self):
        return u'%s' % (self.title)

    def get_absolute_url(self):
        dt = self.pub_date.strftime("%Y/%b/%d")
        return "/content/e/%s/%s/%s/" % (
            dt.lower(), self.publication.slug, self.slug
        )

    # def get_publication_url(self):
    #     """
    #     TODO: used in detail view / template, can be removed
    #     """
    #     return self.publication.get_absolute_url()

    def set_slug(self):
        """
        Auto-populate an empty slug field from the Entry title
        """
        if not self.slug:
            # Where self.name is the field used for 'pre-populate from'
            self.slug = slugify(self.title)

    # def set_tags(self, tags):
    #     Tag.objects.update_tags(self, tags)

    # def get_tags(self):
    #     return Tag.objects.get_for_object(self)

    def get_pub_date_ISO(self):
        """
        returns the publish date in the ISO 8601 format: YYYY-MM-DDTHH:MM:SSZ
        """
        return (self.pub_date - timedelta(
            hours=5, minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")

    def get_created_on_ISO(self):
        """
        returns the creation date time in the ISO 8601 format: YYYY-MM-DDTHH:MM:SSZ
        """
        return (self.created_on - timedelta(
            hours=5, minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")

    def get_updated_on_ISO(self):
        """
        returns the updateion date time in the ISO 8601 format: YYYY-MM-DDTHH:MM:SSZ
        """
        return (self.updated_on - timedelta(
            hours=5, minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")

    # yahoo NITF xml generation helpers.
    def get_created_on_NITF(self):
        """
        returns the creation date time in the ISO 8601:2000 format: YYYYMMDDTHHMMSSZ
        """
        return (self.created_on - timedelta(
            hours=5, minutes=30)).strftime("%Y%m%dT%H%M%SZ")

    # yahoo NITF xml generation helper.
    def get_updated_on_NITF(self):
        """
        returns the updateion date time in the ISO 8601:2000 format: YYYYMMDDTHHMMSSZ
        """
        return (self.updated_on - timedelta(
            hours=5, minutes=30)).strftime("%Y%m%dT%H%M%SZ")

    def get_pub_date_IST(self):
        """
        returns the published date, time
        """
        return (self.pub_date).strftime("%Y%m%dT%H%M%S")

    def get_publication(self):
        """
        TODO: not required
        """
        return self.publication.title

    def _url(self):
        if self.url:
            return "<a href='%s' target='_blank'>%s</a>" % (self.url, self.url)
        else:
            return u"NA"

    _url.allow_tags = True
    _url.short_description = "Story URL"

    def prepare_industry_tagger_item(self):
        return {'id': u'%d-syndication' % self.id,
                'title': self.title,
                'body': self.body_html}


    def _rss_url(self):
        return "<a href='%s' target='_blank'>RSS</a>" % (self.rss_feed.rss_url)

    _rss_url.allow_tags = True

    def save(self, *args, **kwargs):
        """
        1. set the slug
        2. if created for the first time - autotag the content
        3. Add autotag, keywords etc to tags
        """
        self.set_slug()

        # make sure you force convert to utf-8,
        # for body and excerpt use smart_unicode
        self.title = pre_process_data(
            self.title, remove_tags='all', clean_html=False
        )

        # invoke get_body, to strip out basic tags
        self.body_html = pre_process_data(self.body_html)

        # if self.publication.id == 108 and (re.search(
        #         "Lippo", self.title) or re.search("Lippo", self.body_html)):
        #     self.status = -1

        # lets get the list of merged list to be checked in body_html
        mergedWordsList = MergedWord.objects.values_list('name', flat=True)
        if self.body_html:
            for word in mergedWordsList:
                p = re.compile(r'\b' + word + r'\b', re.IGNORECASE)
                foundWord = p.search(self.body_html)
                if foundWord:
                    self.body_html = re.sub(
                        "%s" % foundWord.group(),
                        "<span style='border-bottom: medium double #0101DF'>%s</span>" % foundWord.group(),
                        self.body_html
                    )
                    self.status = 1
                    self.status_reason = 4
                elif self.status_reason == 4:
                    self.status_reason = 0

        # truncate sub heading, keywords to 255 chars
        if self.sub_headline:
            self.sub_headline = truncate(
                pre_process_data(self.sub_headline, remove_tags='all'), 252)
        if self.keywords:
            self.keywords = truncate(
                pre_process_data(self.keywords, remove_tags='all'), 252)

        if self.excerpt:
            self.excerpt = pre_process_data(self.excerpt)

        if self.by_line:
            self.by_line = pre_process_data(self.by_line, remove_tags='all')

        if self.date_line:
            self.date_line = pre_process_data(self.date_line)

        super(Entry, self).save()

        # update the Qs and TransmissionQItems each time you save an entry


    def get_nitf_body(self):
        """
        return cleaned nitf standard body as per yahoo
        """
        from cutils.utils import purify_html
        allowed_tags = [
            # paragraphs and blocks
            'block', 'bq', 'br', 'hr', 'p', 'pre',
            # inline markup
            'a', 'em', 'q', 'sub', 'sup',
            # descriptive lists
            'dl', 'dt', 'dd',
            # unordered (bullet) lists
            'ul', 'li',
            # ordered (numbered) lists
            'ol',
            # story section header
            'hl2',
            # tables
            'col', 'colgroup', 'table', 'tbody', 'td', 'ftoot', 'th', 'thead'
        ]
        return purify_html(self.body_html, allowed_tags)

    def get_credit_line(self):
        """
        returns the credit line of the Entry, if it exists, else default
        Publication copyright is used. Code has been modified to ensure
        that the credit line gets updated for each save.
        For existing Entries this method should be used
        """
        if not self.credit_line:
            return self.publication.get_copyright(self.pub_date, self.body_html)
        return self.credit_line

    def word_count(self):
        """returns the number of words in the body"""
        return len(self.body_html.split())

    def disclaimer(self):
        """returns the disclaimer associated with the Publication"""
        if self.publication.disclaimer:
            return 'DISCLAIMER: %s' % self.publication.disclaimer