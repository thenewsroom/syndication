# TODO: remove BatchModelAdmin code
"""
Revision History
Kapil B     03-Nov-2009    Performance fix for TransmissionQItemAdmin
Kapil B     12-Jun-2009
* Removed BatchModelAdmin code
* TransmissionQs: Added auto-schedule, moved qs to horizontal display
"""

import datetime

from django.contrib import admin

from queues.models import (
    TagRule, TransmissionQ, TransmissionQItem, UploadLocation,KeywordTransmissionQ
)


class TagRulesInline(admin.TabularInline):
    model = TagRule
    extra = 3
    verbose_name_plural = "Select Tag rules wisely: Filter by all and Exclude are db heavy!"


class QAdmin(admin.ModelAdmin):
    list_display = ('title', 'tags', 'items_age', 'published_no_later_than')
    search_fields = ['title', 'tags']
    prepopulated_fields = {"slug": ('title',)}

    fieldsets = ((None, {'fields': (('title', 'slug'), 'tags')}),
                 ('Age of Q Items', {'fields': ('items_age', 'published_no_later_than'),
                                     'classes': ['collapse']}),
                 )

    inlines = [TagRulesInline]


# admin.site.register(Q, QAdmin)

class UploadLocationInline(admin.TabularInline):
    model = UploadLocation
    max_num = 1


class TransmissionQAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'buyer', 'load_frequency', 'active',)
    search_fields = ['title']
    list_filter = ('active', 'auto_schedule', 'buyer')
    prepopulated_fields = {"slug": ('title',)}
    filter_horizontal = ('sub_publications', 'filter_publications')
    fieldsets = [
        (None, {'fields': [('title', 'slug', 'active'),
                           'buyer', ('auto_schedule', 'load_frequency', 'override_last_updated',)]}),
        ('Subscribed Publications', {'fields': ['sub_publications'], 'classes': ['collapse']}),
        # ('Subscribed Industry Feeds', {'fields': ['industry_feeds'], 'classes': ['collapse']}),
        # ('Subscribed Queues',       {'fields': ['qs', 'filter_publications'], 'classes': ['collapse']}),
        ('XML File Generation properties', {
            'fields': [('strip_images', 'file_per_publication', 'file_per_industry')],
        })
    ]

    # actions = ['transmit', 'refresh_q_items']
    # need more testing for transmit!
    actions = ['refresh_q_items']

    def refresh_q_items(modeladmin, request, queryset):
        selected = request.POST.getlist(admin.ACTION_CHECKBOX_NAME)
        objects = queryset.filter(pk__in=selected)
        for obj in objects:
            obj.refresh()

    def transmit(self, request, queryset):
        selected = request.POST.getlist(admin.ACTION_CHECKBOX_NAME)
        objects = queryset.filter(pk__in=selected)

        for obj in objects:
            rfiles, uid_list_T, uid_list_F = obj.transmit(notify=True)
        self.message_user(request, "Files transmitted. Email has been sent to your id")

    inlines = [
        UploadLocationInline,
    ]


admin.site.register(TransmissionQ, TransmissionQAdmin)


class TransmissionQItemAdmin(admin.ModelAdmin):
    list_display = (
        'transmission_id', 'created_on', 'created_by', 'scheduled_on', 'scheduled_by', 'action',
    )
    search_fields = ['entry__id', 'entry__title', ]
    list_filter = ('action', 'created_on', 'tx_q', 'publication', 'created_by')
    fieldsets = (
        (None, {'fields': ('entry', 'action')}),
    )

    list_select_related = False
    list_per_page = 100
    date_hierarchy = 'created_on'

    # entry being a foreignkey will be loaded in a drop-down by default! this will result in
    # out of memory in the server (we are adding 30-50K records / month)
    # just show the entry id, keep it simple
    raw_id_fields = ("entry",)

    # lets set the default admin story list
    def changelist_view(self, request, extra_context=None):
        """
        """
        # set the default year
        if not request.GET.has_key('created_on__year') and not (
                request.GET.has_key('created_on__lte') or request.GET.has_key(
            'created_on__gte') or request.GET.has_key('created_on__month')):
            q = request.GET.copy()
            q['created_on__year'] = u"%d" % datetime.date.today().year

            # set the default month
            q['created_on__month'] = u"%d" % datetime.date.today().month

            request.GET = q
            request.META['QUERY_STRING'] = request.GET.urlencode()
        return super(TransmissionQItemAdmin, self).changelist_view(request, extra_context=extra_context)

    def queryset(self, request):
        """
        On listing page, by default always show data created in the given month
        Override the query, unless user selects the year and month,
        """
        qs = super(TransmissionQItemAdmin, self).queryset(request).only(
            'id', 'tx_q', 'publication', 'action', 'entry', 'created_on')
        if not (request.GET.has_key('created_on__year') or
                request.GET.has_key('created_on__month')):
            now = datetime.datetime.now()
            qs = qs.filter(created_on__year=now.year,
                           created_on__month=now.month,
                           # created_on__day=now.day
                           )
        qs = qs.select_related('tx_q', 'entry', 'publication')
        return qs

    actions = ['schedule', 'ignore', 'make_pending']

    def schedule(modeladmin, request, queryset):
        queryset.update(action='S')

    def ignore(modeladmin, request, queryset):
        queryset.update(action='I')

    def make_pending(modeladmin, request, queryset):
        queryset.update(action='P')


admin.site.register(TransmissionQItem, TransmissionQItemAdmin)


class KeywordTransmissionQAdmin(admin.ModelAdmin):
    list_display = ('title', 'buyer', 'load_frequency')
    search_fields = ['title', 'buyer', 'qs', 'sub_publications']
    list_filter = ('buyer',)
    prepopulated_fields = {"slug": ('title',)}
    filter_horizontal = ('qs', 'sub_publications', 'filter_publications')
    fieldsets = [
        (None, {'fields': [('title', 'slug', 'override_last_updated'), 'buyer', ('auto_schedule', 'load_frequency')]}),
        ('Subscribed Publications', {'fields': ['sub_publications'], 'classes': ['collapse']}),
        ('Keyword Filters', {'fields': ['black_list', 'white_list'], 'classes': ['collapse']}),
        ('File Generation properties', {
            'fields': [('strip_images',)],
        })
    ]
    inlines = [
        UploadLocationInline,
    ]


admin.site.register( KeywordTransmissionQ, KeywordTransmissionQAdmin)


# class IndustryFeedAdmin(admin.ModelAdmin):
#     list_display = ('name', 'created_on', 'updated_on', 'active',)
#     search_fields = ['name']
#     list_filter = ('active', 'created_on', 'updated_on')
#     fieldsets = ((None, {'fields': (('name', 'slug', 'active',), 'industries')}),)
#     filter_horizontal = ('industries',)

#
# admin.site.register(IndustryFeed, IndustryFeedAdmin)




