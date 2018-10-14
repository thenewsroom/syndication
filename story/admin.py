import datetime
from django.db.models import Q

from django.db import models
from django.contrib import admin
from django import forms
from django.forms import CheckboxSelectMultiple
from tinymce.widgets import AdminTinyMCE

from story.models import Story, ScrapingRule, Buyer
from story.forms import StoryAdminForm

CUSTOM_PUB_STATUS = (
    (-1, 'Rejected'),
    (0, 'Draft'),
    (1, 'Pending Review'),
)


# class SourceExist(SimpleListFilter):
#     # Human-readable title which will be displayed in the
#     # right admin sidebar just above the filter options.
#     title = _('Source')
#
#     # Parameter for the filter that will be used in the URL query.
#     parameter_name = 'Source'
#
#     def lookups(self, request, model_admin):
#         """
#         Returns a list of tuples. The first element in each
#         tuple is the coded value for the option that will
#         appear in the URL query. The second element is the
#         human-readable name for the option that will appear
#         in the right sidebar.
#         """
#         return (
#             ('at', _('AT')),
#             ('others', _('Others')),
#
#         )
#
#     def queryset(self, request, queryset):
#         """
#         Returns the filtered queryset based on the value
#         provided in the query string and retrievable via
#         `self.value()`.
#         """
#         # sorce may be empty or None
#         # to decide how to filter the queryset.
#         if self.value() == 'others':
#             return queryset.filter(Q(source__source__name=None) | Q(source__source__name=""))
#         elif self.value() == 'at':
#             return queryset.exclude(id__in=queryset.filter(Q(source__source__name=None) | Q(source__source__name="")))
#         return queryset


class StoryAdmin(admin.ModelAdmin):
    formfield_overrides = {
        models.ManyToManyField: {'widget': CheckboxSelectMultiple},
    }
    form = StoryAdminForm
    fieldsets = ((None, {'fields': (
                                    ('title', 'slug'), ('rule_box',), ('comments'),
                                    ('body_text','approved_by',),
                                    ('original_text', 'status',
                                     'pub_date', 'created_by',),
                                    ('url',),
                                    )
                         }
                  ),
                 )

    list_display = ('title', 'pub_date', 'created_by', 'created_on',
                    'approved_by', 'approved_on', 'comments', 'status')
    prepopulated_fields = {"slug": ("title",)}
    # list_editable = ()
    # readonly_fields = ('domain', 'source')
    search_fields = ['title', 'body_text', 'url']
    date_hierarchy = 'created_on'
    list_filter = ('status', 'pub_date', 'created_on', 'approved_on',
                   'created_by',
                   'approved_by')
    list_per_page = 50
    #raw_id_fields = ('domain', 'source')
    save_on_top = True

    def formfield_for_dbfield(self, db_field, **kwargs):
        # increase the size of the text box for title and secondary headline
        if db_field.name in ['title']:
            kwargs['widget'] = forms.Textarea(attrs={'rows': 2, 'cols': 100})
        # customize comment box size
        elif db_field.name in ['rule_box']:
            kwargs['widget'] = forms.Textarea(attrs={'rows': 3, 'cols': 100})
        elif db_field.name in ['comments']:
            kwargs['widget'] = forms.Textarea(attrs={'rows': 2, 'cols': 100})
        elif db_field.name in ['body_text', 'original_text']:
            kwargs['widget'] = forms.Textarea(attrs={'rows': 15, 'cols': 100})
            kwargs['widget'] = AdminTinyMCE

        return super(StoryAdmin, self).formfield_for_dbfield(db_field, **kwargs)

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.rule_box:  # In edit mode
            return ('rule_box',) + self.readonly_fields
        return self.readonly_fields

    # def response_add(self, request, obj, post_url_continue=None):
    #     base_path = u"/admin/story/story/"
    #     if '_addanother' in request.POST:
    #         domain_id = request.POST['domain']
    #         source_id = request.POST['source']
    #         body_text = ""
    #         if domain_id and source_id:
    #             body_text = obj.source.get_leadline_and_source()
    #         query_string = u'add/?domain={}&source={}&body_text={}'.format(
    #             domain_id, source_id, body_text
    #         )
    #         path = base_path + query_string
    #         return HttpResponseRedirect(path)
    #     elif '_continue' in request.POST:
    #         path = u'{}{}/change/'.format(base_path, obj.id)
    #         message = u'The story "{}" was changed successfully. ' \
    #                   u'You may edit it again below.'.format(obj.title)
    #         self.message_user(request, message, level=messages.INFO)
    #         return HttpResponseRedirect(path)
    #     else:
    #         return HttpResponseRedirect(base_path)

    # def response_change(self, request, obj, post_url_continue=None):
    #     base_path = u"/admin/story/story/"
    #     if '_addanother' in request.POST:
    #         domain_id = request.POST['domain']
    #         source_id = request.POST['source']
    #         body_text = ""
    #         if domain_id and source_id:
    #             body_text = obj.source.get_leadline_and_source()
    #         query_string = u'add/?domain={}&source={}&body_text={}'.format(
    #             domain_id, source_id, body_text
    #         )
    #         path = base_path + query_string
    #         return HttpResponseRedirect(path)
    #
    #     elif '_continue' in request.POST:
    #         return super(StoryAdmin, self).response_change(request, obj)
    #     else:
    #         return HttpResponseRedirect(base_path)

    def queryset(self, request):
        """
        user having scraper permission should see stroies created by userself.
        """
        qs = super(StoryAdmin, self).queryset(request).select_related()
        if request.user.is_superuser or request.user.has_perm('story.view_all_story'):
            return qs
        elif request.user.has_perm('story.can_publish_own_story'):
            return qs.filter(created_by=request.user)
        else:
            return qs.filter(created_by=request.user)

    def formfield_for_choice_field(self, db_field, request, **kwargs):
        """override status: can only see Rejected, Draft and Pending Review"""
        if db_field.name == "status" and not \
                (request.user.has_perm('story.can_publish_all_story') or
                 request.user.has_perm('story.can_publish_own_story')):
            kwargs["choices"] = CUSTOM_PUB_STATUS
            return db_field.formfield(**kwargs)
        return super(StoryAdmin, self).formfield_for_choice_field(
            db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if obj.status in [-1, 2]:
            obj.approved_on = datetime.datetime.now()
            obj.approved_by = request.user
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        obj.save()


class ScrapingRuleAdmin(admin.ModelAdmin):
    fieldsets = ((None, {'fields': (('short_name'), ('rule', 'is_active')),
                         }
                  ),
                 )
    list_display = ('short_name', 'rule', 'created_by', 'created_on')

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        obj.save()


class BuyerAdmin(admin.ModelAdmin):
    fieldsets = ((None, {'fields': (('name', 'slug',),
                                    ('syndication_id', 'active')),
                         }
                  ),
                 )
    list_display = ('name', 'slug', 'syndication_id', 'active')
    list_filter = ('active',)
    search_fields = ('name',)


admin.site.register(Buyer, BuyerAdmin)
admin.site.register(ScrapingRule, ScrapingRuleAdmin)
admin.site.register(Story, StoryAdmin)
