from reporting import reports, site
from django.db.models import Count
from queues.models import TransmissionQItem

class TransmissionQItemStatus(reports.DateBaseReport):
    title = 'TransmissionQ Item Status Report (creation date)'
    description = 'Lists the status count of TransmissionQ Items in the system grouped by creation date for each Publication'
    model = TransmissionQItem
    
    dimensions = [
        'tx_q__title',
        'publication__account__title',
        'publication__title',
        'publication__source__title',
        'publication__load_frequency']
    
    group_by = 'action'
    metrics = (('id', Count, 'Total'),)
    
    filter_fields = ['publication__account', 'publication', 'publication__source', 'tx_q']
    filters = []
    order_by = []
    
    date_field = 'created_on'
    date_dimension = ''

site.register('tqi-status', TransmissionQItemStatus)