import datetime

from django import forms
from django.conf import settings
from djutils.ui.jquery.widgets import DatePicker

from queues.models import TransmissionQ, IndustryFeed

from publications.models import Publication
from penseive_entity.models import Industry as PenseiveIndustry


TRANSMISSION_STATUS = (
    ('S', 'Scheduled'),
    ('T', 'Transmitted'),
    ('P', 'Pending'),
    ('I', 'Ignored'),
    ('F', 'Failed'),
)

    
class TransmissionQStatusReportForm(forms.Form):
    """
    Form that represents the advanced filters for TransmissionQ Status Report
    """

    class Media:
        css = {
            'screen': (settings.JQUERY_UI_CSS,)
        }
        js = (
            settings.JQUERY_JS_URL,
            settings.JQUERY_DATE_PICKER,
        )
        
    # initialize the field elements
    end = datetime.date.today()
    start = end.replace(day=1)
    date_field_choices = [
        ('transmitted_on', 'Transmitted On'),
        ('pub_date', 'Pub Date'),
        ('created_on', 'Created On'),
    ]

    # fetch data using date range as per published,created or approved dates.
    date_field = forms.ChoiceField(
        choices=date_field_choices, label="Date Field", required=False
    )
    start_date = forms.DateField(label="Start date", required=True, initial=start,
                                 widget=DatePicker(options={'dateFormat': 'yy-mm-dd', 'minDate': '-6M', 'maxDate': 'D'}))
    end_date = forms.DateField(label="End date", required=True, initial=end,
                               widget=DatePicker(options={'dateFormat': 'yy-mm-dd', 'minDate': '-6M', 'maxDate': '+1D'}))

    # get the form elements
    tx_q = forms.ChoiceField(
        choices=TransmissionQ.objects.filter(active=True).values_list('id', 'title').order_by('id'),
        label="Tx Queue", required=True
    )
    action = forms.ChoiceField(choices=TRANSMISSION_STATUS, label="Status")
    industryfeeds_name = IndustryFeed.objects.filter(active=True).order_by('name')
    industryfeed = forms.ChoiceField(
        choices=[('', '----'), ('yes','Yes'), ('no','No')] + [(i.id, i.name[:30]) for i in industryfeeds_name],
        label="Industry feeds", required=False, initial=''
    )


class SchedulerForm(forms.Form):
    
    class Media:
        css = {
            'screen': (settings.JQUERY_UI_CSS,)
        }
        js = (
            settings.JQUERY_JS_URL,
            settings.JQUERY_DATE_PICKER,
        )
        
    date = datetime.datetime.today()
    #date_field = forms.ChoiceField(choices=[
    #    ('pub_date', 'Pub Date'),
    #], label="Pub Date", required=False,)
    
    #start_date = forms.DateTimeField(required = False, widget = widgets.AdminSplitDateTime())
    start_date = forms.DateField(label="Pub Date", required=True, initial=date,
        widget=DatePicker(options={'dateFormat': 'yy-mm-dd', 'minDate': '-6M', 'maxDate': 'D'}))
    
    end_date = forms.DateField(label="End date", required=True, initial=date,
        widget=DatePicker(options={'dateFormat': 'yy-mm-dd', 'minDate': '-6M', 'maxDate': '+1D'}))
    
    txqs = TransmissionQ.objects.only('title','id').filter(active=True).order_by('id')
    transmissionq_choice = forms.ChoiceField(choices = [('','All')]+[(txq.id, txq.title) for txq in txqs],
        label = "TransmissionQs", required=False, initial='',)
    
    industryfeeds_name = IndustryFeed.objects.filter(active=True).order_by('name')
    industryfeed = forms.ChoiceField(
        choices = [('','All')] + [(i.id, i.name[:30]) for i in industryfeeds_name],
        label="Industry feeds", required=False, initial=''
    )
    
    pub_qs = Publication.objects.all().only("title","id")
    publication_choice = forms.ChoiceField(
        choices=[('','All')]+[(p.id, p.title[:28]) for p in pub_qs],
        label = "Publications", required=False, initial='',)
    
    action = forms.ChoiceField(choices = [
        # ('','All'),
        ('T','Transmitted'),
        ('S','Scheduled'),
        # ('P','Pending'),
        # ('I','Ignored'),
        ('F','Failed'),
        ('C','Created'),
    ],label = "Status", required = False,
        )