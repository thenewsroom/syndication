import datetime

# django
from django.conf import settings
from django.db import models
from django.db import IntegrityError
from django.contrib.auth.models import User

# external apps

# contify
import queues.signals
from accounts.models import Account
from content_management.models import Entry
from cutils.models import CronSettings
from publications.models import Publication

TX_Q_ACTION = (
    ('P', 'Pending'),
    ('I', 'Ignored'),
    ('S', 'Scheduled'),
    ('C', 'Created'),
    ('T', 'Transmitted'),
    ('F', 'Failed')
)

Q_CUSTOMER_TYPE = (
    ('I', 'contify.com'),
    ('E', 'Customer')
)

Q_ITEM_AGE_DAYS = (
    (1, 'published in last 24hrs'),
    (7, 'published in the past one week'),
    (30, 'published in past month'),
    (90, 'published in past 3 months'),
    (180, 'published in past 6 months')
)

TAG_RULE_KEYS = (
    ('A', 'Filter by all'),
    ('F', 'Filter by any'),
    ('E', 'Exclude any'),
    ('S', 'Search by any'),
)

XML_FORMAT = (
    (0, "Default"),
)

UPLOAD_LOCATION_TYPE = (
    ('F', "FTP"),
    ('O', "Others")
)


# Create your models here.


class Q(models.Model):
    title = models.CharField(max_length=255)
    slug = models.SlugField(
        unique=True, help_text='Automatically built from the title.'
    )
    type = models.CharField(max_length=1, choices=Q_CUSTOMER_TYPE)
    items_age = models.IntegerField(
        choices=Q_ITEM_AGE_DAYS, default=7,
        help_text='Each time the Q is saved or any change is made, \
        all items that fall in the above age bucket will be refreshed, keep this number as small as possible'
    )
    published_no_later_than = models.DateTimeField(
        default=datetime.datetime.now() - datetime.timedelta(days=7),
        help_text='You can further refine the age, by selecting a specific date that falls in the age selected above')

    updated_on = models.DateTimeField(auto_now_add=True)
    created_on = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return u'{}'.format(self.title)

    def get_published_no_later_than(self):
        """
        checks if the published_no_later than lies in the items_age range, returns the shortest interval
        """
        items_age = datetime.datetime.now() - datetime.timedelta(days=self.items_age)
        if self.published_no_later_than < items_age:
            return items_age
        return self.published_no_later_than

    def save(self):
        super(Q, self).save()
        # update all entries updated in last x days
        for e in Entry.objects.live().filter(pub_date__gte=self.get_published_no_later_than()):
            qi, created = QItem.objects.get_or_create(entry=e)
            qi.update_qs()


class QItem(models.Model):
    entry = models.ForeignKey(Entry)
    qs = models.ManyToManyField(Q, null=True, blank=True)

    class Meta:
        unique_together = ('entry',)
        ordering = ('-entry__pub_date',)

    def __unicode__(self):
        return u'%s' % (self.entry)

    def update_qs(self):
        for i in self.qs.all():
            self.qs.remove(i)

        # traverse all valid Qs and check if our entry is valid
        for q in Q.objects.all():
            if q.is_valid(self.entry.tags):
                self.qs.add(q)


class TagRulesManager(models.Manager):
    def filter_all(self, q):
        return self.filter(q=q).filter(key='A')

    def filter_any(self, q):
        return self.filter(q=q).filter(key='F')

    def search(self, q):
        return self.filter(q=q).filter(key='S')

    def exclude(self, q):
        return self.filter(q=q).filter(key='E')

    def filter_rules(self, q):
        """
        return the list of rules that indicate "filtering" of data rather than exclusion, positive
        """
        return self.filter(q=q).exclude(key='E')

    def exclude_rules(self, q):
        """
        return the list of rules that indicate "exclusion" of data, negative
        """
        return self.filter(q=q).filter(key='E')


class TagRule(models.Model):
    q = models.ForeignKey(Q)
    key = models.CharField(max_length=1, choices=(TAG_RULE_KEYS), default='A',
                           help_text="Select rule and enter the values, use (,) to enter multiple tags in the same rule")
    value = models.CharField(max_length=100)
    fetch = TagRulesManager()

    class Meta:
        verbose_name_plural = 'Tag Rules'


class TransmissionQManager(models.Manager):
    def user_tx_qs(self, user):
        """
        get the list of transmission qs that belong to the publications to
        which the user has access to
        """
        return TransmissionQ.objects.filter(
            sub_publications__in=Publication.objects.user_publications(user)). \
            distinct().order_by('title')


# class IndustryFeed(models.Model):
#     name = models.CharField(max_length=200, db_index=True)
#     slug = models.SlugField(max_length=200, unique=True, db_index=True)
#     active = models.BooleanField(default=True)
#     industries = models.ManyToManyField(
#         PensieveIndustry, related_name='industry_feed_set', null=True, blank=True
#     )
#     created_on = models.DateTimeField(auto_now_add=True, null=True, blank=True)
#     updated_on = models.DateTimeField(auto_now_add=True, null=True, blank=True)
#     created_by = models.ForeignKey(User, related_name='created_industry_feeds',
#                                    blank=True, null=True)
#     updated_by = models.ForeignKey(User, related_name='updated_industry_feeds',
#                                    blank=True, null=True)
#
#     def __unicode__(self):
#         return self.name


class TransmissionQ(models.Model):
    title = models.CharField(max_length=75)
    slug = models.SlugField(max_length=75)
    buyer = models.ForeignKey(Account, limit_choices_to={'type': 'B'})
    load_frequency = models.ForeignKey(CronSettings)
    auto_schedule = models.BooleanField(default=False)

    sub_publications = models.ManyToManyField(
        Publication, related_name="sub_publications",
        null=True, blank=True,
        help_text="Selected Publications will be transmitted without filteration"
    )
    qs = models.ManyToManyField(Q, null=True, blank=True)

    filter_publications = models.ManyToManyField(
        Publication, related_name="filter_publications",
        null=True, blank=True,
        help_text="The Selected Q results will be filtered for these publications only"
    )

    refine_tags = models.TextField(
        help_text="Enter sets of tags within double quotes to further refine on the Qs",
        blank=True
    )

    override_last_updated = models.BooleanField(
        default=False,
        help_text="If checked, will pull all data since the begining of the Q or Publication. \
                    If unchecked, will pull only those items that were created since the last refresh"
    )

    updated_on = models.DateTimeField(auto_now_add=True)
    strip_images = models.BooleanField(default=True)
    file_per_publication = models.BooleanField(default=True)
    file_per_industry = models.BooleanField(default=True)
    active = models.BooleanField(default=False, db_index=True)
    objects = TransmissionQManager()

    class Meta:
        verbose_name_plural = 'Transmission Qs'
        unique_together = ('slug', 'buyer')

    def __unicode__(self):
        return u'%s' % (self.title)

    def fetch_q_items(self):
        p = None
        if self.filter_publications.all():
            p = self.filter_publications.all()

        last_updated_on = None
        if not self.override_last_updated:
            last_updated_on = self.updated_on

        qitems = QItem.objects.none()
        for q in self.qs.all():
            qitems = qitems | q.fetch_items(
                publications=p, last_updated_on=last_updated_on
            )

        return qitems

    def q_items(self):
        """
        returns the list [q, (entry)]
        """
        if self.filter_publications.all():
            if not self.override_last_updated:
                return [(q, q.items(publications=self.filter_publications.all(),
                                    last_updated_on=self.updated_on)) for q in self.qs.all()
                        ]
            else:
                return [(q, q.items(
                    publications=self.filter_publications.all())) for q in self.qs.all()
                        ]
        else:
            if not self.override_last_updated:
                return [(q, q.items(
                    last_updated_on=self.updated_on)) for q in self.qs.all()
                        ]

        # return all items that belong to the selected q!
        return [(q, q.items()) for q in self.qs.all()]

    def get_industry_ids(self):
        industry_ids = set()
        industry_feed_qs = self.industry_feeds.all()
        for industry_feed in industry_feed_qs:
            industry_ids.update(
                list(industry_feed.industries.values_list('id', flat=True))
            )
        return industry_ids

    def sub_pub_items(self):
        """
        returns the list of Entries [entry]
        """
        if self.sub_publications.exists() or self.industry_feeds.exists():
            eqs = Entry.objects.live()
            if self.sub_publications.exists():
                eqs = eqs.filter(publication__in=self.sub_publications.all())
            if not self.override_last_updated:
                eqs = eqs.filter(created_on__gte=self.updated_on)
            if self.industry_feeds.exists():
                industry_ids = self.get_industry_ids()
                eqs = eqs.filter(penseive_industry__id__in=industry_ids)
            if self.pk == 3:
                eqs = eqs.filter(send_to_factiva=True)
            return eqs
        return []

    def add_items(self, qs, action=None):
        """
        Manually add transmissionQItems from the queryset
        TODO: use this function to add items during refresh()
        if all goes well, returns True, else False
        """
        if not action:
            action = 'P'
            if self.auto_schedule:
                action = 'S'

        # if invalid action, set it to 'P'
        if action not in ['P', 'S']:
            action = 'P'

        # assuming qs belongs to the Entry model
        # this is where we should throw an exception
        if not qs.model == Entry:
            return False

        # ensure that the entries in the queryset belong to the transmissionq!!
        q_pub_ids = self.sub_publications.values_list(
            'id', flat=True
        )
        qs = qs.filter(publication__id__in=q_pub_ids)

        # # commenting below given line to add a entry in industry feed
        # # queue because industry is not added to entry yet

        # if self.industry_feeds.exists():
        #     industry_ids = self.get_industry_ids()
        #     qs = qs.filter(penseive_industry__id__in=industry_ids)
        if self.pk == 3:
            qs = qs.filter(send_to_factiva=True)

        for e in qs.iterator():
            try:
                tx_q_item, created = TransmissionQItem._default_manager.get_or_create(
                    tx_q=self, entry=e, action=action
                )
            except IntegrityError, e:
                # do nothing entry exists
                pass
        return True

    def refresh(self):
        """
        Refresh the TransmissionQItems, fetch data from subscribed publications and queues
        """
        # if a publication is selected - pull all the items that belong to that publication
        # in this queue and set the action to "Schedule" by default
        for e in self.sub_pub_items().iterator():
            try:
                tx_q_item, created = TransmissionQItem._default_manager.get_or_create(tx_q=self, entry=e)
            except IntegrityError, e:
                # do nothing entry exists
                pass
            if created:
                tx_q_item.action = 'S'
                tx_q_item.save()
            # else already exists, do nothing ...

        # for each q that belongs to this buyer, add the corresponding entries to the
        # respective TransmissionQItem, keep default action ie Pending for now
        for qi in list(set(self.fetch_q_items())):
            e = qi.entry
            q = qi.qs.all()[:1][0]
            try:
                tx_q_item, created = TransmissionQItem._default_manager.get_or_create(tx_q=self, q=q, entry=e)
                if created and self.auto_schedule:
                    tx_q_item.action = 'S'
                    tx_q_item.save()
            except IntegrityError, e:
                # do nothing, pass
                pass

        # update the last updated_on time to today
        # this will ensure next time when the queue is refreshed, existing data is excluded
        # will set it to start of current day, possible things might be in progress during refresh
        today = datetime.datetime.today()
        self.updated_on = datetime.datetime(year=today.year, month=today.month, day=today.day)
        self.save()

    def refresh_old(self):
        """
        Populate entries for a given tx_q
        TODO
        fetch entries that were created since the last update on this q was done
        OR refresh all entries OR put integrity constraints
        """

        # update the last updated_on
        self.updated_on = datetime.datetime.now()

        # if a publication is selected - pull all the items that belong to that publication
        # in this queue and set the action to "Schedule" by default
        for e in self.sub_pub_items():
            try:
                tx_q_item, created = TransmissionQItem._default_manager.get_or_create(tx_q=self, entry=e)
            except IntegrityError, e:
                # do nothing entry exists
                pass
            if created:
                tx_q_item.action = 'S'
                tx_q_item.save()
            # else already exists, do nothing ...

        # for each q that belongs to this buyer, add the corresponding entries to the
        # respective TransmissionQItem, keep default action ie Pending for now
        for q, es in self.q_items():
            if es:
                for e in es:
                    try:
                        tx_q_item, created = TransmissionQItem._default_manager.get_or_create(tx_q=self, q=q, entry=e)
                        if created and self.auto_schedule:
                            tx_q_item.action = 'S'
                            tx_q_item.save()
                    except IntegrityError, e:
                        # do nothing, pass
                        pass

    def get_absolute_url(self):
        return "/content/q/txq/%s/" % (self.slug)

    def get_tqi_status_count(self, start_date=datetime.date.today(), end_date=datetime.datetime.now(),
                             action=[], by_pub_date=False):
        """
        returns the status of the TransmissionQItems, transmitted in the given range
        date range filter is by default applied on the created_on date of TransmissionQItem
        if by_pub_date is True, date range filter is applied on Entry pub_date
        """
        qs = TransmissionQItem.objects.filter(tx_q=self)

        if by_pub_date:
            qs = qs.filter(entry__pub_date__range=(start_date, end_date))
        else:
            qs = qs.filter(created_on__range=(start_date, end_date))

        # apply the action filter, if present
        if action:
            qs = qs.filter(action__in=action)

        return qs.values('action', 'publication__account__title',
                         'publication__title', 'publication__slug'). \
            annotate(c=models.Count('action')). \
            order_by('action', 'publication__account__title', 'publication__title')

    def transmit(self, notify=False):
        """
        transmit scheduled objects, if ftp location is present
        """
        try:
            uid_list_T = []
            uid_list_F = []

            up_loc = UploadLocation.objects.get(tx_q=self)

            tq_items = TransmissionQItem.scheduled_objects.filter(tx_q=self)
            for tqi in tq_items:
                try:
                    uid, xml = tqi.xml()
                    ftp.upload_content(uid + ".xml", xml)
                    tqi.action = "T"
                    uid_list_T.append(tqi.entry.title + " [ " + tqi.entry.title + " ]")
                except Exception, e:
                    tqi.action = "F"
                    uid_list_F.append(tqi.entry.title + " [ " + tqi.entry.title + " ]")

                tqi.save()

            rdir, rfiles = ftp.listdir("/")
            ftp.disconnect()

            # send a confirmation email if all looks good!
            if notify:
                from django.core.mail import send_mail
                subject = "File Upload Status - %s | %02d" \
                          % (self.buyer, len(uid_list_T))

                body = "%s\nItems transmitted:\n%s\n%s\n" % (
                "=".ljust(40, "="), "=".ljust(40, "="), "\n".join(uid_list_T))
                body = body + "%s\nItems failed:\n%s\n%s\n" % (
                "=".ljust(40, "="), "=".ljust(40, "="), "\n".join(uid_list_F))
                body = body + "%s\nFiles in remote dir:\n%s\n%s\n" % (
                "=".ljust(40, "="), "=".ljust(40, "="), "\n".join(rfiles))
                body = body + settings.EMAIL_DEFAULT_SIGNATURE

                send_mail(subject, body, settings.DEFAULT_FROM_EMAIL,
                          [settings.DELIVERY_EMAIL], fail_silently=True)

            return rfiles, uid_list_T, uid_list_F

        except:
            return 0


class ScheduledItemsManager(models.Manager):
    def get_query_set(self):
        return super(ScheduledItemsManager, self).get_query_set().filter(action='S')


class TransmittedItemsManager(models.Manager):
    def get_query_set(self):
        return super(TransmittedItemsManager, self).get_query_set().filter(action='T')


class PendingItemsManager(models.Manager):
    def get_query_set(self):
        return super(PendingItemsManager, self).get_query_set().filter(action='P')


class TransmissionQItem(models.Model):
    items = models.Manager()
    objects = models.Manager()
    scheduled_objects = ScheduledItemsManager()
    transmitted_objects = TransmittedItemsManager()
    pending_objects = PendingItemsManager()

    tx_q = models.ForeignKey(
        TransmissionQ, limit_choices_to={'active': True}
    )
    q = models.ForeignKey(Q, null=True)
    entry = models.ForeignKey(Entry)
    publication = models.ForeignKey(
        Publication, null=True, limit_choices_to={'active': True}
    )
    action = models.CharField(max_length=1, choices=TX_Q_ACTION, default='P')
    xml_format = models.IntegerField(choices=XML_FORMAT, default=0)
    created_on = models.DateTimeField(auto_now_add=True, db_index=True)
    created_by = models.ForeignKey(
        User, default=1, related_name="created_tqitem_set",
        limit_choices_to={'is_active': True, 'is_staff': True}
    )
    scheduled_on = models.DateTimeField(auto_now_add=True, db_index=True)
    scheduled_by = models.ForeignKey(
        User, default=1, related_name="schedulded_tqitem_set",
        limit_choices_to={'is_active': True, 'is_staff': True}
    )

    def __unicode__(self):
        return u'%s' % (self.transmission_id())

    class Meta:
        verbose_name_plural = 'Transmission Q Items'
        unique_together = ('tx_q', 'entry')
        ordering = ('-created_on',)

    def update_status(self, action=None):
        if not action:
            action = 'S'
        self.action = action

    def schedule(self):
        self.action = 'S'

    def transmission_id(self):
        tx_id = "[%s] [%s]: %s_%d" % (
            self.tx_q.slug.upper(), self.publication.slug.upper(), self.entry.title, self.entry.id)
        return tx_id

    def save(self, *args, **kwargs):
        """
        update the publication
        """
        self.publication = self.entry.publication
        super(TransmissionQItem, self).save()

    def xml(self):
        """
        deprecated - a view is now available in cms to generate the xml
        use: cms.views.xmlobj_list
        returns the XML in the selected format
        """

        # check the buyer and inoke the app XML gen module!
        if self.xml_format == 1:
            pass
        else:
            from queues.utils import default

            return default(self.entry, self.transmission_id())


class UploadLocation(models.Model):
    type = models.CharField(max_length=1, choices=UPLOAD_LOCATION_TYPE, default='F')
    tx_q = models.ForeignKey(TransmissionQ)
    location = models.CharField(max_length=300)

    class Meta:
        ordering = ('type',)

    def __unicode__(self):
        return u'%s' % (self.location)


class KeywordTransmissionQ(TransmissionQ):
    "transmission Q based on black list and white list"
    black_list = models.TextField(blank=True, null=True)
    white_list = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name_plural = 'Transmission Qs (Keyword Based)'




