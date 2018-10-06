from django.contrib import admin
from django import forms

from publications.models import (Publication, FeedLoadStatus, PublicationLoadStatus,
                                 RichFeed, FeedFormat, FeedScreenshot,
                                 PublicationStatus)

# from queues.models import TransmissionQ
# from mptt.forms import TreeNodeMultipleChoiceField
from django.utils.translation import ugettext_lazy
# from mptt.admin import MPTTModelAdmin

admin.site.register(FeedFormat)

class RichFeedInline(admin.TabularInline):
    model = RichFeed
    extra = 1
    #exclude = ['title']
    fieldsets = ((None, {'fields': (('title', 'rss_url', '_rss_url', 'web_url', '_web_url', 'active',),
                                    )
                         }
                  ),
                 )
    readonly_fields = ('_rss_url', '_web_url')

class PublicationStatusInline(admin.TabularInline):
    model = PublicationStatus
    extra = 1

class PublicationAdmin(admin.ModelAdmin):

    list_display = ('title', 'slug', 'account', 'auto_schedule',)
    list_editable = ('auto_schedule', )
    search_fields = ['title', 'account__title']
    list_filter = ('auto_schedule', 'active', 'account',)
    prepopulated_fields = {"slug": ('title', )}
    fieldsets = ((None, {'fields': (('title', 'slug', 'description',),
                                    ('account', 'created_on',),
                                    ('disclaimer', 'copyright',),
                                    ('auto_schedule',
                                     'feed_format', 'active')
                                    )
                         }
                  ),
                 )
    readonly_fields = ('created_on',)
    # filter_horizontal = ('section',)
    inlines = [RichFeedInline, PublicationStatusInline]

admin.site.register(Publication, PublicationAdmin)

class FeedLoadStatusAdmin(admin.ModelAdmin):
    list_display = ('publication', 'filename', 'status', 'comments', 'created_on')
    search_fields = ['comments', 'filename']
    list_filter = ('created_on', 'status', 'publication',)

admin.site.register(FeedLoadStatus, FeedLoadStatusAdmin)

class PublicationLoadStatusAdmin(admin.ModelAdmin):
    list_display = ('publication', 'start_time', 'end_time', 'load_status', 'load_count', 'reject_count')
    search_fields = ['title', 'comments', 'publication__slug']
    list_filter = ('load_date', 'load_status', 'publication')

admin.site.register(PublicationLoadStatus, PublicationLoadStatusAdmin)

class FeedScreenshotAdmin(admin.ModelAdmin):
    list_display = ('title', 'rss_feed', 'created_on',)
    search_fields = ['title']
    list_filter = ('created_on',)

admin.site.register(FeedScreenshot, FeedScreenshotAdmin)

class PublicationStatusAdmin(admin.ModelAdmin):
    list_display = ('publication', 'client', 'status')
    search_fields = ['publication__title']
    list_filter = ('status', 'client', 'publication')

admin.site.register(PublicationStatus, PublicationStatusAdmin)

