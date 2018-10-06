import re

from django.contrib import admin
from django.http import HttpResponseRedirect
from django.utils.translation import ugettext_lazy as _
from django.contrib.admin import SimpleListFilter
from django.forms import Textarea
from django.db import models

from .spider import Spider
from .forms import WebsourceAdminForm
from .models import (SourceAccount, Source, SourceUrl,
                              SourceUrlStatus, SourceStatus)


class DocCounterFilter(SimpleListFilter):
    # Human-readable title which will be displayed in the
    # right admin sidebar just above the filter options.
    title = _('doc counter')

    # Parameter for the filter that will be used in the URL query.
    parameter_name = 'doc_counter'

    def lookups(self, request, model_admin):
        """
        Returns a list of tuples. The first element in each
        tuple is the coded value for the option that will
        appear in the URL query. The second element is the
        human-readable name for the option that will appear
        in the right sidebar.
        """
        return (
            ('< 1', _('< 1')),
            ('1 - 2', _('1 - 2')),
            ('2 - 5', _('2 - 5')),
            ('5 - 10', _('5 - 10')),
            ('10 - 1000', _('10 - 1000')),
            ('>= 1000', _('>= 1000')),
        )

    def queryset(self, request, queryset):
        """
        Returns the filtered queryset based on the value
        provided in the query string and retrievable via
        `self.value()`.
        """
        # Compare the requested value (either '80s' or '90s')
        # to decide how to filter the queryset.
        if self.value() == '< 1':
            return queryset.filter(doc_counter__lt=1)
        if self.value() == '1 - 2':
            return queryset.filter(doc_counter__gte=1, doc_counter__lt=2)
        if self.value() == '2 - 5':
            return queryset.filter(doc_counter__gte=2, doc_counter__lt=5)
        if self.value() == '5 - 10':
            return queryset.filter(doc_counter__gte=5, doc_counter__lt=10)
        if self.value() == '10 - 1000':
            return queryset.filter(doc_counter__gte=10, doc_counter__lt=1000)
        if self.value() == '>= 1000':
            return queryset.filter(doc_counter__gte=1000)


class TagDetailExistsFilter(SimpleListFilter):
    # Human-readable title which will be displayed in the
    # right admin sidebar just above the filter options.
    title = _('Tag Detail Exists')

    # Parameter for the filter that will be used in the URL query.
    parameter_name = 'tag_detail_exists'

    def lookups(self, request, model_admin):
        """
        Returns a list of tuples. The first element in each
        tuple is the coded value for the option that will
        appear in the URL query. The second element is the
        human-readable name for the option that will appear
        in the right sidebar.
        """
        return (
            ('yes', _('Yes')),
            ('no', _('No')),
        )

    def queryset(self, request, queryset):
        """
        Returns the filtered queryset based on the value
        provided in the query string and retrievable via
        `self.value()`.
        """
        # Compare the requested value (either '80s' or '90s')
        # to decide how to filter the queryset.
        if self.value() == 'yes':
            return queryset.filter(tag_name__isnull=False)
        elif self.value() == 'no':
            return queryset.filter(tag_name__isnull=True)
        else:
            return queryset


class SourceAccountAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ['name']
    fieldsets = ((None, {'fields':
                             (('name', 'slug'),
                              'url_to_update', 'account_type', 'notify_to'
                              )
                         }
                  ),
                 )
    prepopulated_fields = {"slug": ("name",)}
    filter_horizontal = ('notify_to',)


admin.site.register(SourceAccount, SourceAccountAdmin)


class SourceUrlInline(admin.StackedInline):
    model = SourceUrl
    extra = 1
    template = "admin/websource/sourceurl/edit_inline/stacked.html"
    fieldsets = ((None, {'fields':
                             (('name', 'url', 'is_updated'),
                              ('uid', 'tag_name', 'tag_attr', 'tag_attr_value'),
                              'need_triage'
                              )
                         }
                  ),
                 )
    readonly_fields = ('old_snapshot', 'new_snapshot',)


class SourceAdmin(admin.ModelAdmin):
    list_display = ('name', 'assigned_to', 'total_url', 'need_triage', 'manual_triage', 'to_do', 'nodocs',
                    'is_integrated', 'is_active')
    # list_editable = ('frequency',)
    search_fields = ['name', 'sid']
    list_filter = ('account', 'is_active', 'is_integrated', 'created_on', 'assigned_to')

    fieldsets = ((None, {'fields':
                             (('name', 'slug', 'sid', 'is_active', 'is_integrated'),
                              ('account', 'assigned_to', 'same_as',),
                              # ('exclude_tag', 'exclude_tag_attr', 'exclude_tag_attr_value'),
                              )
                         }
                  ),
                 )
    date_hierarchy = 'created_on'
    actions = ['mark_integrated', 'mark_active']

    def get_actions(self, request):
        actions = super(SourceAdmin, self).get_actions(request)
        if not request.user.is_superuser:
            actions = []
        return actions

    def get_list_display(self, request):
        list_display = super(SourceAdmin, self).get_list_display(request)
        if not request.user.is_superuser:
            list_display = ('name', 'assigned_to', 'manual_triage', 'total_url', 'to_do',)
        return list_display

    # def get_list_filter(self, request):
    #     list_filter = super(SourceAdmin, self).get_list_filter(request)
    #     if not request.user.is_superuser:
    #         list_filter = ('assigned_to',)
    #     return list_filter

    def get_prepopulated_fields(self, request, obj=None):
        pp_fields = super(SourceAdmin, self).get_prepopulated_fields(request)
        # if request.user.is_superuser:
        pp_fields = {"slug": ("name",)}
        return pp_fields

    # def get_fieldsets(self, request, obj=None):
    #     fieldsets = super(SourceAdmin, self).get_fieldsets(request, obj)
    #     if not request.user.is_superuser:
    #         fieldsets = ((None, {'fields': (('name',),)}),)
    #     return fieldsets

    # def get_readonly_fields(self, request, obj=None):
    #     read_only_fields = super(SourceAdmin, self).get_readonly_fields(request)
    #     if not request.user.is_superuser:
    #         read_only_fields = ('name',)
    #     return read_only_fields

    def mark_integrated(self, request, queryset):
        rows_updated = queryset.update(is_integrated=True)
        self.message_user(request, """
                          %s item(s) successfully marked as integrated.
                          """ % (rows_updated))
        return HttpResponseRedirect(request.get_full_path())

    def mark_active(self, request, queryset):
        rows_updated = queryset.update(is_active=True)
        self.message_user(request, """
                          %s item(s) successfully marked as active.
                          """ % (rows_updated))
        return HttpResponseRedirect(request.get_full_path())

    def queryset(self, request):
        """
        just to categorize contify and tns sources
        """
        qs = super(SourceAdmin, self).queryset(request).select_related()
        if request.user.is_superuser or request.user.has_perm('websource.view_all'):
            return qs
        elif request.user.has_perm('websource.access_contify_source'):
            return qs.filter(account__slug__exact='contify')
        elif request.user.has_perm('websource.access_tns_source'):
            return qs.filter(account__slug__exact='tns')


admin.site.register(Source, SourceAdmin)


class SourceUrlAdmin(admin.ModelAdmin):
    form = WebsourceAdminForm
    formfield_overrides = {
        models.TextField: {'widget': Textarea(attrs={'rows': 4, 'cols': 100})}
    }
    template = "admin/websource/sourceurl/change_form.html"
    list_display = ('source', 'status', 'aid_link', 'published_count', 'is_checked', 'need_triage',
                    'last_doc_found_on', 'is_updated', 'last_triaged', 'is_working')

    fieldsets = ((None, {'fields':
                             (('uid', 'url', 'is_active', 'is_checked',), ('name',),
                              ('tag_name', 'tag_attr', 'tag_attr_value', 'is_updated', 'overwrite',),
                              ('source', 'last_triaged', 'is_working', 'need_triage', 'manual_triage',),
                              ('status', 'response_code', 'response_msg', 'doc_counter', 'nodoc_counter',),
                              ('specific_rule',), ('scraping_rules',),
                              ('old_snapshot', 'new_snapshot',),
                              )
                         }
                  ),
                 )
    search_fields = ['name', 'uid', 'url']
    list_filter = ('status', 'source__account', 'is_active', 'is_checked',
                   'is_updated', 'need_triage', 'manual_triage', 'created_on', 'tag_updated_on',
                   'is_working', 'last_triaged', TagDetailExistsFilter, 'created_by',
                   'updated_by', 'response_code', 'source',
                   )
    list_editable = ('is_checked',)
    filter_horizontal = ('scraping_rules',)
    readonly_fields = ('old_snapshot', 'new_snapshot', 'last_triaged',
                       'need_triage', 'response_code', 'response_msg', 'doc_counter', 'nodoc_counter',
                       'status',
                       )
    date_hierarchy = 'created_on'
    actions = ['mark_updated', 'mark_todo', 'fetch_patent_urls']
    list_per_page = 100

    def lookup_allowed(self, key, value):
        """
        To bypass the security check altogether
        """
        return True

    # def get_actions(self, request):
    #     actions = super(SourceUrlAdmin, self).get_actions(request)
    #     if not request.user.is_superuser:
    #         actions = []
    #     return actions

    # def get_list_filter(self, request):
    #     list_filter = super(SourceUrlAdmin, self).get_list_filter(request)
    #     if not request.user.is_superuser:
    #         list_filter = ('status', 'is_checked',)
    #     return list_filter

    # def get_fieldsets(self, request, obj=None):
    #     fieldsets = super(SourceUrlAdmin, self).get_fieldsets(request, obj)
    #     if not request.user.is_superuser:
    #         fieldsets = ((None, {'fields': (('name',),)}),)
    #     return fieldsets

    # def get_readonly_fields(self, request, obj=None):
    #     read_only_fields = super(SourceUrlAdmin, self).get_readonly_fields(request)
    #     if not request.user.is_superuser:
    #         read_only_fields = ('name',)
    #     return read_only_fields

    def get_list_display(self, request):
        list_display = super(SourceUrlAdmin, self).get_list_display(request)
        if not request.user.is_superuser:
            list_display = ('source', 'status', 'last_checked', 'aid_link',
                            'published_count', 'last_doc_found_on', 'is_checked',
                            'is_updated', 'last_triaged')
        return list_display

    def fetch_patent_urls(self, request, queryset):
        rows_updated = queryset.update(manual_triage=True)
        self.message_user(request, """
                          %s item(s) successfully marked for scraping.
                          """ % (rows_updated))
        return HttpResponseRedirect(request.get_full_path())

    def mark_updated(self, request, queryset):
        rows_updated = queryset.update(is_updated=True)
        self.message_user(request, """
                          %s item(s) successfully marked as updated.
                          """ % (rows_updated))
        return HttpResponseRedirect(request.get_full_path())

    def mark_todo(self, request, queryset):
        rows_updated = queryset.update(is_updated=True, is_checked=False)
        self.message_user(request, """
                          %s item(s) successfully added in todo list.
                          """ % (rows_updated))
        return HttpResponseRedirect(request.get_full_path())

    def save_model(self, request, obj, form, change):
        if obj.overwrite:
            spider = Spider()
            dTup = spider.fetch_page_data(obj.url)
            html_data, resCode, resMsg = dTup
            content_tag = spider.get_content_tag(html_data, tag_name=obj.tag_name,
                                                 tag_attr=obj.tag_attr,
                                                 tag_attr_value=obj.tag_attr_value,
                                                 )
            plaintext = spider.get_text(content_tag)
            resMsg = u''
            if resMsg == "NOT FOUND":
                resMsg = "PAGE NOT FOUND"
            if re.search("NAME OR SERVICE NOT KNOWN", resMsg):
                resMsg = "INTERNAL SERVER ERROR"
            obj.response_code = resCode
            obj.response_msg = resMsg
            obj.save(new_snapshot=plaintext)
        if not obj.is_checked:
            obj.is_checked = True
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        obj.save()

    def queryset(self, request):
        """
        just to categorize contify and tns sources
        """
        qs = super(SourceUrlAdmin, self).queryset(request).select_related()
        if request.user.is_superuser or request.user.has_perm('websource.view_all'):
            return qs
        elif request.user.has_perm('websource.access_contify_source'):
            return qs.filter(source__account__slug__exact='contify')
        elif request.user.has_perm('websource.access_tns_source'):
            return qs.filter(source__account__slug__exact='tns')


admin.site.register(SourceUrl, SourceUrlAdmin)


class SourceUrlStatusAdmin(admin.ModelAdmin):
    list_display = ('sourceurl', '_source', 'comment', 'created_on', 'status',)
    search_fields = ['sourceurl__url', 'comment']
    list_filter = ('status', 'created_on', 'sourceurl__source__account', 'sourceurl__source')
    fieldsets = ((None, {'fields':
                             (('sourceurl', 'status'), ('comment',),
                              )
                         }
                  ),
                 )
    readonly_fields = ('sourceurl', 'status', 'comment')
    list_per_page = 500


admin.site.register(SourceUrlStatus, SourceUrlStatusAdmin)


class SourceStatusAdmin(admin.ModelAdmin):
    list_display = ('source', '_sid', 'created_on', 'status',)
    search_fields = ['source__name']
    list_filter = ('status', 'created_on', 'source__account',)
    fieldsets = ((None, {'fields':
                             (('source', 'status'),
                              )
                         }
                  ),
                 )
    readonly_fields = ('source', 'status')


admin.site.register(SourceStatus, SourceStatusAdmin)
