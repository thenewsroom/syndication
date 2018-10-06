# from django.contrib import admin
# from penseive_entity.models import Industry
# from mptt.admin import MPTTModelAdmin
#
#
# class IndustryAdmin(MPTTModelAdmin):
#     search_fields = ['name', 'id']
#     list_display = ('name', 'parent', 'active')
#     list_filter = ('active', 'parent',)
#     list_editable = ('parent', 'active')
#     list_per_page = 50
#     raw_id_fields = ("parent",)
#
#     def queryset(self, request):
#         """
#         Provides searching on keyword only for name property.
#         Provides two methods to search:
#         1. "^" => any keyword starts with search
#         2. "=" => any keyword exact search
#
#         TODO # Can be extended to run on slug also
#         """
#         qs = super(IndustryAdmin, self).queryset(request)
#         query_dict = request.GET.copy()
#         name = request.GET.get('q', None)
#         if name is not None:
#             try:
#                 int(name[1::])
#                 if name.startswith('^'):
#                     query_dict['q'] = name.split('^')[-1]
#                     request.GET = query_dict
#                     request.META['QUERY_STRING'] = request.GET.urlencode()
#                     return qs.filter(id__startswith=name.split('^')[-1])
#
#                 elif name.startswith('='):
#                     query_dict['q'] = name.split('=')[-1]
#                     request.GET = query_dict
#                     request.META['QUERY_STRING'] = request.GET.urlencode()
#                     return qs.filter(id__exact=name.split('=')[-1])
#                 else:
#                     return qs
#             except ValueError:
#                 if name.startswith('^'):
#                     query_dict['q'] = name.split('^')[-1]
#                     request.GET = query_dict
#                     request.META['QUERY_STRING'] = request.GET.urlencode()
#                     return qs.filter(name__istartswith=name.split('^')[-1])
#
#                 elif name.startswith('='):
#                     query_dict['q'] = name.split('=')[-1]
#                     request.GET = query_dict
#                     request.META['QUERY_STRING'] = request.GET.urlencode()
#                     return qs.filter(name__iexact=name.split('=')[-1])
#                 else:
#                     return qs
#         return qs
#
#     def save_model(self, request, obj, form, change):
#         if not change:
#             obj.created_by = request.user
#         obj.save()
#
#
# admin.site.register(Industry, IndustryAdmin)