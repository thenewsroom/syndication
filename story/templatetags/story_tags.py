from django import template


def prepare_query_string(val):
    query_string = u''
    if val.get('created_by__id'):
        query_string += u'created_by__id__exact={}'.format(
                val.get('created_by__id')
        )
    else:
        query_string += u'&created_by__id__isnull=True'
    if val.get('approved_by__id'):
        query_string += u'&approved_by__id__exact={}'.format(
                val.get('approved_by__id')
        )
    else:
        query_string += u'&approved_by__id__isnull=True'

    if val.get('alternate_domain__id'):
        query_string += u'&alternate_domain__id__exact={}'.format(
                val.get('alternate_domain__id')
        )
    return query_string

register = template.Library()
register.filter('prepare_query_string', prepare_query_string)