# python's inbuits
import datetime

# import django related
from django.db import models
from django.contrib.auth.models import User
from django.template.defaultfilters import slugify

# Create your models here.

PUB_STATUS = (
    (-1, 'Rejected'),
    (0, 'Draft'),
    (1, 'Pending Review'),
    (2, 'Published'),
)


class Buyer(models.Model):
    name = models.CharField(max_length=250)
    slug = models.CharField(max_length=250)
    syndication_id = models.IntegerField()
    active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('slug', 'syndication_id')

    def __unicode__(self):
        return self.name

    def get_unique_token(self):
        return u'{}-{}'.format(self.slug, self.syndication_id)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super(Buyer, self).save()


class Story(models.Model):
    """
    To store articles scraped from source (agency) urls.
    """
    REJECTED = -1
    DRAFT = 0
    PENDING_REVIEW = 1
    PUBLISHED = 2

    title = models.CharField('Headline', max_length=800, db_index=True)
    slug = models.SlugField(max_length=300, unique=True)
    body_text = models.TextField(blank=True, null=True)
    original_text = models.TextField(blank=True, null=True)
    pub_date = models.DateTimeField('Date published', db_index=True)
    status = models.IntegerField(choices=PUB_STATUS, default=0, db_index=True)
    url = models.URLField(max_length=800, db_index=True, unique=True)
    created_on = models.DateTimeField(db_index=True)
    created_by = models.ForeignKey(User, default=8, related_name="created_story_set")
    updated_on = models.DateTimeField(db_index=True)
    approved_on = models.DateTimeField(db_index=True, blank=True, null=True)
    approved_by = models.ForeignKey(
        User, related_name="approved_story_set", blank=True, null=True
        )
    comments = models.TextField(blank=True)
    rule_box = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "Stories"
        ordering = ['-pub_date']

        permissions = (
            ("view_all_story", "View All Stories"),
            ("can_publish_own_story", "Can publish own story"),
            ("can_publish_all_story", "Can publish all story"),
        )

    def __unicode__(self):
        return u'%s' % (self.title)

    def get_pub_date_ISO(self):
        """
        returns the publish date in the ISO 8601 format: YYYY-MM-DDTHH:MM:SSZ
        """
        return (self.pub_date - datetime.timedelta(hours=5, minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")

    def get_pub_date_IST(self):
        """
        returns the published date, time
        """
        return (self.pub_date).strftime("%Y%m%dT%H%M%S")

    def body_html(self):
        return u"".join([u"<p>%s</p>" % line.strip() for line in
                         self.body_text.split('\n') if line.strip()])


    def save(self, *args, **kwargs):
        """
        custom changes before actual save
        """
        if self.title and not self.slug:
            self.slug = slugify(self.title)

        if not self.created_on:
            self.created_on = datetime.datetime.now()
        self.updated_on = datetime.datetime.now()
        super(Story, self).save(*args, **kwargs)


class ScrapingRule(models.Model):
    """
    To store scraping rules.
    Eg: Third Party: Don't upload from Bloomberg, IANS etc.
    """
    short_name = models.CharField(max_length=200)
    rule = models.TextField()
    created_on = models.DateTimeField()
    updated_on = models.DateTimeField()
    created_by = models.ForeignKey(User, default=8, related_name="created_scraping_rules")
    updated_by = models.ForeignKey(User, default=8, related_name="updated_scraping_rules")
    is_active = models.BooleanField(default=True)

    def __unicode__(self):
        return unicode(self.short_name)

    def save(self, *args, **kwargs):
        if not self.created_on:
            self.created_on = datetime.datetime.now()
        self.updated_on = datetime.datetime.now()
        super(ScrapingRule, self).save()

