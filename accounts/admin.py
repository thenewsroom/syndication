from django.contrib import admin

from accounts.models import Account, AccountUserProfile, Agreement


class AgreementInline(admin.TabularInline):
    model = Agreement
    extra = 1
    exclude = ['expires_on']


class AgreementAdmin(admin.ModelAdmin):
    list_display = ('account', 'signed_on', 'expires_on', 'revenue_share', 'term', 'billing_frequency', 'auto_renewal',)
    date_hierarchy = 'signed_on'
    list_filter = ('auto_renewal', 'billing_frequency', 'expires_on')


admin.site.register(Agreement, AgreementAdmin)


class AccountUserProfileInline(admin.TabularInline):
    model = AccountUserProfile
    extra = 2
    exclude = ['address_line1', 'address_line2', 'country']
    
    
class AccountUserProfileAdmin(admin.ModelAdmin):
    list_display = ('poc', 'account', 'last_name', 'first_name', 'user', 'email', 'phone')
    search_fields = ['account', 'last_name', 'first_name', 'country']
    list_filter  = ('poc', 'account', )
    fieldsets    = [
        (None, {'fields': [('account', 'poc')]}),
        ('User Details', {'fields': [('title', 'first_name', 'last_name'), \
            'position', ('email', 'phone')]}),
        ('Address - optional - leave blank, if same as Account', {'fields': [('address_line1', 'address_line2', 'country')]}),
        (None, {'fields': ['user']})
    ]
admin.site.register(AccountUserProfile, AccountUserProfileAdmin)    

    
class AccountAdmin(admin.ModelAdmin):
    search_fields = ['title']
    list_filter = ('type', )
    list_display = ('title', 'slug', 'type', )
    prepopulated_fields = {"slug": ('title', )}
    #save_on_top = True
    fieldsets = [(None, {'fields': [('type', 'title', 'slug')]}),
        ('Customer Details', {
            'fields': [
                ('client_poc', 'client_email'),
                ('client_add_line1', 'client_add_line2', 'client_country')
                ],
            'classes': ['collapse']}),
        ('Notes', {'fields': [('notes')], 'classes': ['collapse']})
    ]

    inlines = [
        AccountUserProfileInline,
    ]    
admin.site.register(Account, AccountAdmin)
