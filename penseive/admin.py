from django.contrib import admin
from django import forms

from penseive.models import Industry, Entity, EntityType
from penseive.models import PenseiveItem, EntityItem, QuoteItem
from django.http import HttpResponseRedirect

admin.site.register(Industry)


class EntityTypeAdmin(admin.ModelAdmin):
    search_fields = ['name', ]
    list_display = ('name', 'source', 'relevance_threshold', 'active',)
    list_filter = ('active', 'source',)
    list_editable = ('relevance_threshold', 'active',)


admin.site.register(EntityType, EntityTypeAdmin)


class EntityAdminForm(forms.ModelForm):
    class Meta:
        model = Entity
        fields = "__all__"

    def clean_active(self):
        active = self.cleaned_data['active']
        if not active:
            child_entities = self.instance.get_child_entities().values_list('name', flat=True)
            if len(child_entities) > 0:
                raise forms.ValidationError(
                    'Found child entities: %s, please remove all the references and then try deactivating it' % child_entities)
        return active

    def clean_display_name(self):
        display_name = self.cleaned_data["display_name"]
        if not self.instance.validate_display_name(display_name):
            raise forms.ValidationError(
                'Display name is valid for parent entities only! Either define this as a parent entity by setting Same as to blank or remove the display name')
        return display_name

    def clean_same_as(self):
        same_as = self.cleaned_data["same_as"]
        if same_as:
            if not self.instance.validate_same_as(same_as):
                raise forms.ValidationError(
                    'Please ensure that Same as being referred to is a parent, active and belongs to the same type')

            # check if entity is a parent, if not, make sure child entities do not exist
            if not self.instance.id == same_as.id:
                child_entities = self.instance.get_sameas_child_entities().values_list('name', flat=True)
                if len(child_entities) > 0:
                    raise forms.ValidationError(
                        'Found child entities: %s, please remove all the references and then try setting the same as' % child_entities)

        return same_as


class EntityAdmin(admin.ModelAdmin):
    form = EntityAdminForm
    list_select_related = True
    search_fields = ['name', 'type__name', ]
    list_display = ('name', 'type', 'parent', 'same_as', 'display_name', 'status', 'active',)
    list_filter = ('active', 'status', 'created_on', 'type',)
    list_editable = ('display_name', 'same_as', 'parent', 'status',)
    list_per_page = 50
    raw_id_fields = ("same_as", "parent",)

    # actions = ['make_inactive']
    #
    # def make_inactive(self, request, queryset):
    #    entities_updated = queryset.update(active=False)
    # if entities_updated == 1:
    #    message_bit = "1 entity was"
    # else:
    #    message_bit = "%s entities were" % entities_updated
    #    self.message_user(request, "%s successfully marked as inactive." % message_bit)
    # return HttpResponseRedirect(request.get_full_path())


admin.site.register(Entity, EntityAdmin)


class EntityItemInline(admin.TabularInline):
    model = EntityItem
    list_select_related = True
    raw_id_fields = ('entity', 'type',)
    list_display = ('type', 'entity', 'relevance',)
    list_filter = ('active', 'type')
    fieldsets = (
        (None, {'fields': ('entity', 'type', 'relevance', 'active')}),
    )
    extra = 3


class PenseiveItemAdmin(admin.ModelAdmin):
    list_select_related = True
    inlines = [
        EntityItemInline
    ]


admin.site.register(PenseiveItem, PenseiveItemAdmin)


class QuoteItemAdmin(admin.ModelAdmin):
    list_select_related = True
    search_fields = ['quote_text', 'entity__type__name', ]
    list_display = ('quote_text', 'entity', 'potential_match', 'active',)
    list_filter = ('active', 'created_on',)
    list_editable = ('entity', 'potential_match', 'active',)
    list_per_page = 50
    raw_id_fields = ('entity', 'potential_match', 'penseive_item',)


admin.site.register(QuoteItem, QuoteItemAdmin)