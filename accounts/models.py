# core python
import time
from datetime import timedelta, date

# django
from django.db import models
from django.conf import settings
from django.contrib.auth.models import User

# Create your models here.

FREQUENCY = (
    ('D', 'Daily'),
    ('W', 'Weekly'),
    ('M', 'Monthly'),
    ('Q', 'Quarterly'),
    ('Y', 'Yearly'),
)

ACCOUNT_TYPE = (
    ('P', 'Content Provider'),
    ('B', 'Content Buyer'),
)

BUYER_TYPE = (
    ('S', 'Subscription'),
    ('W', 'Web'),
    ('P', 'Print'),
    ('A', 'All / Multiple combos of the above')
)

USER_PROFILE_POC = (
    ('A', 'Account'),
    ('R', 'Royalty'),
    ('T', 'Technical')
)

USER_PROFILE_TITLE = (
    (1, 'Mr'),
    (2, 'Mrs'),
    (3, 'Ms'),
    (4, 'Dr'),
    (5, 'Prof'),
    (6, 'Other'),
)

BILLING_FREQUENCY = (
    ('M', 'Monthly'),
    ('Q', 'Quarterly'),
)

CURRENCY = (
    ('USD', 'US Dollars'),
    ('GBP', 'Pounds'),
    ('EUR', 'Euros'),
    ('INR', 'Indian Ruppee'),
)

TERMS = (
    (1, '1 year'),
    (2, '2 years'),
    (3, '3 years'),
    (4, '4 years'),
    (5, '5 years'),
)


class Account(models.Model):
    title = models.CharField(max_length=75)
    slug = models.SlugField(
        max_length=350,
        # unique_for_date='pub_date',
        help_text='Automatically built from the title.'
    )
    type = models.CharField(max_length=1, choices=ACCOUNT_TYPE)
    copyright = models.CharField(max_length=255, null=True)
    company_contact = models.CharField(
            max_length=255, default=settings.COMPANY_CONTACT
    )
    
    client_poc = models.CharField\
        (max_length=75, blank=True, help_text="Name (Point of Contact)"
         )
    client_add_line1 = models.CharField(
            max_length=100, blank=True, help_text="Street Address, Apt #"
    )
    client_add_line2 = models.CharField(
            max_length=100, blank=True, help_text="City, State, ZIP"
    )
    client_country = models.CharField(max_length=75, blank=True)
    client_email = models.EmailField(max_length=100, blank=True)
    
    notes = models.TextField(
            blank=True, help_text="Capture any notes / comments"
    )
        
    class Meta:
        ordering = ('title',)
        
    def __unicode__(self):
        return u'{}'.format(self.title)

    def get_absolute_url(self):
        return u"/account/{}/".format(self.slug)

    def get_copyright(self):
        if not self.copyright:    
            return "Copyright %s %s, distributed by %s" % (
                time.strftime("%Y", time.localtime()), self.title,
                settings.COMPANY_NAME
            )
    
    def get_all_publications(self):
        return self.publication_set.all()

class AccountUserProfile(models.Model):
    poc = models.CharField(max_length=1, choices=USER_PROFILE_POC)
    title = models.IntegerField(choices=USER_PROFILE_TITLE)
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    email = models.EmailField(max_length=100)
    phone = models.CharField(
            max_length=20, blank=True,
            help_text=u"{}{}".format(
                    "Mention the country code and area code ",
                    "eg. +91 9811098110, +91 11 4106677"
            )
    )
    position = models.CharField(max_length=75, blank=True)
    address_line1 = models.CharField(
            max_length=100, blank=True, help_text="Street Address, Apt #"
    )
    address_line2 = models.CharField(
            max_length=100, blank=True, help_text="City, State, ZIP"
    )
    country = models.CharField(max_length=20, blank=True)
    user = models.ForeignKey(User,  null=True, blank=True)
    account = models.ForeignKey(Account)
    
    class Meta:
        ordering  = ('last_name',)
    
    def __unicode__(self):
        return u'{}, {}'.format(self.last_name, self.first_name)


class Agreement(models.Model):
    signed_on = models.DateField()
    expires_on = models.DateField(
        blank=True,
        help_text="Will be calculated from the term, if left blank"
    )
    term = models.PositiveIntegerField(choices=TERMS)
    revenue_share = models.PositiveIntegerField(
        help_text="Providers revenue share in %"
    )
    billing_frequency = models.CharField(
        max_length=1, choices=BILLING_FREQUENCY
    )
    auto_renewal = models.BooleanField(default=False)
    account = models.ForeignKey(Account)
    currency = models.CharField(max_length=3, choices=CURRENCY)
    tds_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)

    class Meta:
        ordering = ('account__title',)

    def __unicode__(self):
        return u'{} ({}-{})'.format(
            self.account.title, self.signed_on.strftime('%d-%b-%Y'),
            self.expires_on.strftime('%d-%b-%Y')
        )