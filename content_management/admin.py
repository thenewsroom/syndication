import datetime

from django import forms
from django.conf import settings
from django.db import models
from django.contrib import admin

from django.http import HttpResponseRedirect
from django.utils.encoding import smart_unicode, DjangoUnicodeDecodeError
from django.forms.utils import ErrorList

# for the sections widget includes.
from django.forms import widgets, Textarea, CheckboxSelectMultiple
# from django.forms.util import flatatt
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy
# checkbox input widget includes.
from itertools import chain
from django.utils.encoding import force_unicode
from django.utils.html import conditional_escape

# from cms.models import Entry, Source, ManualEntry, Industry, Journal, MergedWord
# above line is commented as Industry is not in use
from content_management.models import Entry, MergedWord
from publications.models import Publication
# from tagging.models import Tag
# from tagging.fields import TagField
from tinymce.widgets import AdminTinyMCE

# from queues.models import TransmissionQItem
# from industrytagger import IndustryTagger
# from penseive_entity.models import Industry as PenseiveIndustry
# from cutils.utils import unicode_to_ascii
# from cms.custom_admin_filters import CustomIndustryFilter

# Globally disable delete selected
# admin.site.disable_action('delete_selected')
SCRAPER_PUB_STATUS = (
    (0, 'Draft'),
    (1, 'Pending Review'),
)

class EntryAdminForm(forms.ModelForm):
    """
    Added for pub_date custom validation on Manual Entry screen
    """

    class Meta:
        fields = "__all__"
        model = Entry

    def __init__(self, *args, **kwargs):
        """
        Check if Entry instance is there in kwargs or not
        If it is not there and if there is a publication ID in args
        then prepare the section TreeNodeMultipleChoiceField for ajax call
        """
        super(EntryAdminForm, self).__init__(*args, **kwargs)
        try:
            pub_id = args[0].__getitem__('publication')
            if not pub_id.isdigit():
                pub_id = None
        except IndexError:
            pub_id = None
        try:
            instance = kwargs.__getitem__('instance')
        except KeyError:
            instance = None

    def clean(self):
        """
        ensures that the slug is unique across the publication and pub date
        """
        super(EntryAdminForm, self).clean()
        cleaned_data = self.cleaned_data
        pub_date = cleaned_data.get("pub_date")
        publication = cleaned_data.get("publication")
        slug = cleaned_data.get("slug")
        if not publication:
            raise forms.ValidationError("Publication cannot be null")

        # check if the slug is unique for the publication and date
        #qs = Entry.objects.filter(slug=slug, publication=publication,
        #                          pub_date__year=pub_date.year,
        #                          pub_date__month=pub_date.month,
        #                          pub_date__day=pub_date.day
        #                          )
        qs = Entry.objects.only('id').filter(
            slug=slug, publication=publication, status=2
            )
        if self.instance:
            qs = qs.exclude(id=self.instance.id)

        if qs:
            raise forms.ValidationError(
                mark_safe("""Potential duplicate: Entry with same slug already exists. ID: %s
                          """ % ("".join(
                            ["<p><a href='/admin/cms/entry/%d/' target='_blank'>%d</a></p>" % (
                                i, i) for i in list(qs.values_list('id', flat=True))])))
                )
        status = cleaned_data.get("status")
        d = datetime.datetime.now().replace(hour=23,minute=59,second=59, microsecond=0)
        if status == 2:
            if pub_date > d:
                self._errors['pub_date'] = ErrorList([mark_safe("Pubdate can't be future date")])
        return cleaned_data


class EntryAdmin(admin.ModelAdmin):
    """
    If you want to use a custom widget with a relation field (i.e. ForeignKey or ManyToManyField),
    make sure you haven't included that field's name in  raw_id_fields or radio_fields.
    formfield_overrides won't let you change the widget on relation fields
    that have raw_id_fields or  radio_fields set.
    That's because  raw_id_fields and radio_fields imply custom widgets of their own.
    """

    form = EntryAdminForm
    list_display = ('title', 'by_line', 'pub_date', '_created_on', 'approved_on', 'publication',
                    'created_by', 'approved_by', 'word_count', 'status',
                    'industry_rejected_news', 'translated_content',)

    search_fields = ['title', 'body_html', 'by_line']
    list_filter = ('status', 'created_on', 'approved_on', 'updated_on',
                   'status_reason',
                   'publication', 'created_by', 'approved_by')
    prepopulated_fields = {"slug": ("title",)}
    fieldsets = (
        (None, {'fields': (('title', 'slug',), ('comments',),
                           ('publication', 'status', 'pub_date',),
                           ('body_html', 'approved_by', 'approved_on',),
                           ('url', '_url'), ('_rss_url'), ('issue_no', 'volume_no', 'author'),
                           ('by_line', 'credit_line', 'date_line'),
                           )
                }),
    )

    radio_fields = {"status": admin.HORIZONTAL}
    readonly_fields = ('approved_by', 'approved_on', '_url', '_rss_url')
    # raw_id_fields = ('industry', )
    # filter_horizontal = ('penseive_industry',)
    list_per_page = 100
    list_select_related = True
    date_hierarchy = 'pub_date'
    save_as = True
    save_on_top = True

    # this is required for auto-completion
    related_search_fields = {
        'publication': ('title',),
    }

    def _created_on(self, obj):
        """
        to show in admin display list without microsecond!
        """
        return obj.created_on.replace(microsecond=0)

    _created_on.admin_order_field = 'created_on'

    def formfield_for_dbfield(self, db_field, **kwargs):
        # use TinyMCE widget for body_html
        if db_field.name == 'body_html':
            kwargs['widget'] = AdminTinyMCE
        # increase the size of the text box for title and secondary headline
        elif db_field.name in ['title', 'sub_headline']:
            kwargs['widget'] = forms.TextInput(attrs={'size': '90'})
        if db_field.name in ['excerpt', 'comments']:
            kwargs['widget'] = forms.TextInput(attrs={'size': '90'})
        if db_field.name in ['title', 'comments']:
            kwargs['widget'] = forms.Textarea(attrs={'rows': 2, 'cols': 100})
        return super(EntryAdmin, self).formfield_for_dbfield(db_field, **kwargs)
    #
    # def get_urls(self):
    #     """
    #     add foreignkey_autocomplete pattern to url,
    #     django_extensions.admin ForeignKeyAutocompleteAdmin uses __call__ which
    #     uses admin.site.root (deprecated module) for url patterns
    #     """
    #     from django.conf.urls.defaults import patterns, url
    #
    #     urls = super(EntryAdmin, self).get_urls()
    #     my_urls = patterns('', url(r'^foreignkey_autocomplete/$',
    #                                self.admin_site.admin_view(
    #                                    self.foreignkey_autocomplete)))
    #     return my_urls + urls


    actions = ['will_be_pending', 'will_be_published',]
    #actions = ['make_pending']

    def will_be_pending(self, request, queryset):
        rows_updated = queryset.update(status='1')
        self.message_user(request, "%s item(s) successfully marked as pending." % (rows_updated))
        return HttpResponseRedirect(request.get_full_path())

    def will_be_published(self, request, queryset):
        # queryset.update(status='2')
        rows_updated = 0
        for obj in queryset:
            obj.approved_on = datetime.datetime.now()
            obj.approved_by = request.user
            obj.status = 2
            obj.save()
            rows_updated = rows_updated + 1

            # transmit the publish with user signal

        self.message_user(request, "%s item(s) successfully marked as published." % (rows_updated))
        return HttpResponseRedirect(request.get_full_path())


    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user

        if obj.status in [-1, 2] and not obj.approved_by:
            obj.approved_on = datetime.datetime.today()
            obj.approved_by = request.user
        obj.save()
admin.site.register(Entry, EntryAdmin)

class MergedWordAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ['name']
    list_filter = ('created_on',)
    fieldsets = ((None, {'fields': (('name',),)}),)

    def save_model(self, request, obj, form, change):
        """update the created_by"""
        if not obj.created_by:
            obj.created_by = request.user
        super(MergedWordAdmin, self).save_model(request, obj, form, change)

admin.site.register(MergedWord, MergedWordAdmin)




