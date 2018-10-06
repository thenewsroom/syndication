# Create yoiur views here.
# python standard lib imports
import datetime
import logging
import urllib
import simplejson

# django imports
from django.http import Http404
from django.template import RequestContext
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import (
    render, get_object_or_404, render_to_response, HttpResponse
)
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count

# project imports
from story.models import Story, Buyer
from websource.models import Source, SourceAccount
from dateutil.parser import parse
from story.forms import UserMonitorForm



logger = logging.getLogger(__name__)


def prepare_query_filter(form_data):
    """
    :param form_data:
    :return:
    prepares a dict as per form field to db field mapping
    """
    filter_dict = dict()
    start_datetime = form_data.get('start_day')
    if not start_datetime:
        start_datetime = datetime.datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0
        )

    end_datetime = form_data.get('end_day')
    if not end_datetime:
        end_datetime = datetime.datetime.now().replace(
            hour=23, minute=59, second=59
        )

    if form_data.get('status_field'):
        filter_dict['status__exact'] = form_data.get('status_field')

    if form_data.get('source_field'):
        filter_dict['alternate_domain__id__exact'] = form_data.get(
            'source_field'
        )

    if form_data.get('created_by'):
        filter_dict['created_by__id__exact'] = form_data.get(
            'created_by'
        )
    if form_data.get('approved_by'):
        filter_dict['approved_by__id__exact'] = form_data.get(
            'approved_by'
        )

    if form_data.get('date_field'):
        filter_dict['{}__gte'.format(
            form_data.get('date_field'))] = start_datetime
        filter_dict['{}__lte'.format(
            form_data.get('date_field'))] = end_datetime
    return filter_dict


def get_xml_feed(request, domain_id):
    """
    """
    if not domain_id.isdigit:
        raise Http404
    endDate = datetime.datetime.now()
    hours_limit = request.GET.get('h', '2')
    if hours_limit.isdigit():
        hours_limit = int(hours_limit)
    else:
        hours_limit = 2
    startDate = endDate - datetime.timedelta(hours=hours_limit)
    storyQs = Story.objects.select_related()
    domain = get_object_or_404(Source, id=domain_id)
    storyQs = storyQs.filter(alternate_domain=domain, approved_on__gte=startDate, status=2)
    story_count = storyQs.count()
    # results = storyQs.values()
    return render(request, 'story/xml_feed/stories.xml',
                  {'results': storyQs, 'currentDay': datetime.datetime.now(),
                   'domain': domain, 'story_count': story_count,
                   'hours_limit': hours_limit},
                  content_type="application/xhtml+xml"
                  )


@staff_member_required
@csrf_exempt
def user_monitor(request):
    if request.method == 'GET':
        form = UserMonitorForm(request.GET)
        filter_dict = dict()
        if form.is_valid():
            filter_dict = prepare_query_filter(form.cleaned_data)
        else:
            # To Do: action required if form is not valid
            return HttpResponse(
                "Invalid Form data Entered. Try Again with valid data"
            )
        if filter_dict:
            qs = Story.objects.only(
                'id', 'status', 'created_on', 'approved_on', 'updated_on'
            ).select_related('alternate_domain', 'created_by', 'approved_by')

            qs = qs.filter(**filter_dict)
            total_count = qs.count()
            base_query_string = urllib.urlencode(filter_dict)
            result = qs.values(
                'created_by__username', 'created_by__id',
                'approved_by__username', 'approved_by__id',
            ).annotate(c=Count("created_by")).order_by('approved_by')

            return render_to_response(
                'story/user-monitor.html',
                {'form': form, 'result': result, 'total_count': total_count,
                 'base_query_string': base_query_string},
                context_instance=RequestContext(request)
            )
        else:
            form = UserMonitorForm(request.GET)
            return render(request,
                'story/user-monitor.html',
                {'form': form}
            )


def get_buyer_config(request):
    if request.method == 'GET':
        bqs = Buyer.objects.all()
        buyer_list = [{
            'name': b.name,
            'syndication_id': b.syndication_id,
            'token': b.get_unique_token()
        } for b in bqs]
        return HttpResponse(
            simplejson.dumps(buyer_list), content_type="application/json"
        )
    else:
        return Http404