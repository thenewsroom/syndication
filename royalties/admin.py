from django.contrib import admin
from django.http import HttpResponseRedirect
from django.db.models import TextField

from tinymce.widgets import AdminTinyMCE

from royalties.models import Receivable, Payable, Royalty


class RoyaltyAdmin(admin.ModelAdmin):
    list_display = ('account', 'revenue', 'statement_date', 'billing_frequency', 'deliver', 'delivered_on',)
    list_editable = ('deliver',)
    date_hierarchy = 'statement_date'
    list_filter = ('billing_frequency', 'deliver', 'delivered_on', 'account',)
    search_fields = ['account__title']

    formfield_overrides = {
        TextField: {'widget': AdminTinyMCE},
    }

    def get_actions(self, request):
        """ Disable delete_selecetd only """
        actions = super(RoyaltyAdmin, self).get_actions(request)
        del actions['delete_selected']
        return actions

    actions = ['update_revenue', ]

    def update_revenue(self, request, queryset):
        for obj in queryset:
            obj.update_revenue()
            obj.save()
        self.message_user(request, "Revenue updated successfully")
        return HttpResponseRedirect(request.get_full_path())


admin.site.register(Royalty, RoyaltyAdmin)


class PayableAdmin(admin.ModelAdmin):
    actions = None
    list_display = (
    'account', 'publication', 'receivable', 'royalty_statement', 'revenue_share', 'exchange_rate', 'tds_rate',
    'payable',)
    list_filter = ('account',)
    list_editable = ('exchange_rate',)


admin.site.register(Payable, PayableAdmin)


class PayableInline(admin.TabularInline):
    model = Payable
    extra = 10
    exclude = ['revenue_share', 'override_share', 'royalty_statement', 'account', 'payable', 'exchange_rate',
               'tds_rate', ]


class ReceivableAdmin(admin.ModelAdmin):
    actions = None
    list_display = ('title', 'received_from', 'revenue', 'received_on', 'unallocated')
    list_filter = ('received_from',)
    date_hierarchy = 'received_on'
    fieldsets = [
        (None, {'fields': [('received_from', 'title')]}),
        (None, {'fields': [('revenue', 'currency', 'exchange_rate', 'received_on')]}),
        (None, {'fields': [('duration_start', 'duration_end')]})
    ]
    inlines = [
        PayableInline
    ]


admin.site.register(Receivable, ReceivableAdmin)
