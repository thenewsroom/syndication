# TODO: do we need date based views? can be deleted?
# TODO: clean-up, remove commented / dead code
import logging
import csv
import datetime
import itertools
import operator
from datetime import timedelta
from dateutil.parser import parse
from django.conf import settings
from django.views.generic.simple import direct_to_template
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import simplejson
from django.views.generic.list_detail import object_list
from django.views.generic.date_based import archive_index, archive_day, archive_month, archive_year

from django.template import loader, RequestContext
from django.views.decorators.cache import cache_control

from cutils.utils import ContifyDateUtil
from publications.models import Publication
from queues.models import Q, QItem, TransmissionQ, TransmissionQItem, IndustryFeed
from queues.forms import TransmissionQStatusReportForm, SchedulerForm
from penseive_entity.models import Industry as PenseiveIndustry
from reporting.forms import DateBaseReportForm

logger = logging.getLogger(__name__)


def listq(request, slug, pub_slug='all', page=1):
    """
    list the items that belong to the Queue and filtered Publication
    """
    q = get_object_or_404(Q, slug=slug)
    qitems = q.fetch_items()

    # lets get the items filtered by publication
    qitems_pub = qitems
    if pub_slug and pub_slug <> 'all':
        try:
            qitems_pub = qitems.filter(
                entry__publication=Publication.objects.get(slug=pub_slug.strip()))
        except Publication.DoesNotExist, e:
            pass
    else:
        pub_slug = 'all'

    # the final query to be sent to object_list
    items = qitems_pub

    # list of publications that are part of this Q - for side bar
    pub_list = qitems.values('entry__publication__title', 'entry__publication__slug').annotate(
        c=Count('entry__publication')).order_by()

    # get the list of Tags for these items
    tag_list = []

    return object_list(
        request,
        queryset=items,
        paginate_by=settings.PAGINATE_BY_SIZE,
        page=page,
        template_name='q/list.html',
        template_object_name='qitems',
        extra_context={
            'q': q, 'pub_list': pub_list, 'pub_slug': pub_slug, 'tag_list': tag_list
        }
    )


def tx_q_list(request, slug, action='S', q_slug="all", pub_slug='all', page=1):
    """
    list the items that belong to the Transmission Queue and filter by Q and Publications
    """
    # lets define the default datetime range
    startDate = datetime.datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
    endDate = datetime.datetime.today().replace(hour=23, minute=59, second=59)
    date_field = 'transmitted_on'
    tx_q = get_object_or_404(TransmissionQ, slug=slug)
    qitems = TransmissionQItem.objects.filter(
        tx_q=tx_q, action=action).select_related('entry', 'entry__publication')

    if request.method == 'GET':
        if 'created_on__lte' in request.GET and 'created_on__gt' in request.GET:
            try:
                startDate = parse(request.GET.get('created_on__gt'))
                endDate = parse(request.GET.get('created_on__lte')).replace(hour=23, minute=59, second=59)
            except ValueError, e:
                # error with the date format
                # use the default datetime range
                pass
        if 'industryfeed' in request.GET and request.GET.get('industryfeed'):
            industryfeed_id = request.GET.get('industryfeed') or ''
            if industryfeed_id == 'yes':
                available_industries = PenseiveIndustry.objects.filter(active=True).values_list('id', flat=True)
                qitems = qitems.filter(entry__penseive_industry__id__in=available_industries)
            elif industryfeed_id == 'no':
                qitems = qitems.filter(entry__penseive_industry__isnull=True)
            elif not industryfeed_id == '':
                industry_feed = IndustryFeed.objects.get(id=industryfeed_id)
                available_industries = industry_feed.industries.values_list('id', flat=True)
                qitems = qitems.filter(entry__penseive_industry__id__in=available_industries)
            else:
                pass

        date_field = request.GET.get('date_field')
    if date_field == 'transmitted_on':
        qitems = qitems.filter(created_on__gt=startDate, created_on__lte=endDate)
    elif date_field == 'pub_date':
        qitems = qitems.filter(entry__pub_date__gt=startDate, entry__pub_date__lte=endDate)
    else:
        qitems = qitems.filter(entry__created_on__gt=startDate, entry__created_on__lte=endDate)

    # get the list of Qs and the items in each Q
    # TODO get the # of items in each q
    # one way is to [q, q.qitem_set.count() for q in tx_q.qs.all()]
    q_list = tx_q.qs.all()

    # lets get the Q items sorted out first
    # all results will be stored in qs
    if q_slug <> "all":
        q = get_object_or_404(Q, slug=q_slug)
        qitems = qitems.filter(q=q)

    # get the list of filtered publications for this Tx Q, if blank get all Publications
    # list of publications that are part of this Q - for side bar
    # just show those which are part of this Q
    pub_list = qitems.values(
        'publication__title', 'publication__slug'
    ).annotate(c=Count('publication')).order_by()

    # lets get the items filtered by publication, filter on qs
    if pub_slug <> 'all':
        p = get_object_or_404(Publication, slug=pub_slug)
        qitems = qitems.filter(publication=p)

    return object_list(
        request,
        queryset=qitems.distinct(),
        paginate_by=settings.PAGINATE_BY_SIZE,
        page=page,
        template_name='tx_q/list.html',
        template_object_name='qitems',
        extra_context={
            'tx_q': tx_q, 'q_list': q_list,
            'pub_list': pub_list, 'q_slug': q_slug,
            'pub_slug': pub_slug, 'action': action}
    )


def index(request, slug):
    q = get_object_or_404(Q, slug=slug)
    qitems = q.items()

    # check the query string if publication is passed
    pub_slug = request.GET.get('p', '')
    if pub_slug:
        try:
            items = qitems.filter(publication=Publication.objects.get(slug=pub_slug.strip()))
        except Publication.DoesNotExist, e:
            items = qitems
    else:
        items = qitems
        pub_slug = 'All'

    # datelist for month archives on the side bar
    date_list = qitems.filter(pub_date__year=datetime.datetime.now().year).dates('pub_date', 'month')

    # list of publications for side bar
    pub_list = Publication.objects.filter(id__in=qitems.values_list('publication', flat=True).order_by().distinct())

    # allow future stories - Indian Express has certain data that gets published with a future time
    # restrict the data beyond 24hrs in the q.items query set
    return archive_index(
        request,
        queryset=items,
        date_field='pub_date',
        template_name='q/index.html',
        allow_future=True,
        extra_context={'q': q, 'date_list': date_list, 'pub_list': pub_list, 'pub_slug': pub_slug}
    )


def month_index(request, year, month, slug):
    q = get_object_or_404(Q, slug=slug)
    items = q.items()

    # datelist for month archives on the side bar
    date_list = items.filter(pub_date__year=year).dates('pub_date', 'month')

    # allow future stories - Indian Express has certain data that gets published with a future time
    # restrict the data beyond 24hrs in the q.items query set
    return archive_month(
        request,
        year=year,
        month=month,
        queryset=items,
        date_field='pub_date',
        template_name='q/month_index.html',
        allow_future=True,
        extra_context={'q': q, 'date_list': date_list}
    )


def tq_day_index(request, year, month, day, slug):
    # check if the transmission q for the buyer exists!
    tq = get_object_or_404(TransmissionQ, buyer__slug=slug)

    # get list of transmitted and scheduled objects
    tq_qs = TransmissionQItem.scheduled_objects.filter(tx_q__buyer__slug=slug)
    entries = [tqi.entry for tqi in tq_qs]

    return archive_day(
        request,
        year=year,
        month=month,
        day=day,
        queryset=entries,
        date_field='pub_date',
        template_name='q/tq_day_index.html',
        allow_future=True,
        extra_context={'tq': tq}
    )


@login_required
def tx_q_status(request, slug=None):
    # get the transmission q
    if slug:
        tx_q = get_object_or_404(TransmissionQ, slug=slug)
    else:
        tx_q = None

    qs = TransmissionQItem.objects.none()
    count = 0
    action = 'S'
    date_field = 'transmitted_on'
    industryfeed_id = ''
    if request.method == 'GET':
        form = TransmissionQStatusReportForm(request.GET)
        if form.is_valid():
            tx_q_id = form.cleaned_data['tx_q']
            start_date = ContifyDateUtil(form.cleaned_data['start_date']).start()
            end_date = ContifyDateUtil(form.cleaned_data['end_date']).end()
            action = form.cleaned_data['action']
            date_field = form.cleaned_data['date_field']
            industryfeed_id = form.cleaned_data['industryfeed']
            tx_q = TransmissionQ.objects.get(id=tx_q_id)
            qs = TransmissionQItem.objects.filter(
                tx_q__id=tx_q_id).select_related('entry', 'entry__publication')
        else:
            cfy_date = ContifyDateUtil()
            start_date, end_date = cfy_date.month()
            qs = TransmissionQItem.objects.filter(
                tx_q=tx_q).select_related('entry', 'entry__publication')
            if tx_q:
                form = TransmissionQStatusReportForm({
                    'tx_q': tx_q.id,
                    'start_date': start_date.date(),
                    'end_date': end_date.date(),
                    'action': action,
                })  # unbound form

            else:
                form = TransmissionQStatusReportForm()  # unbound form

    # apply the filters
    qs = qs.filter(action=action)
    if date_field == 'transmitted_on':
        qs = qs.filter(created_on__range=(start_date, end_date))
    elif date_field == 'created_on':
        qs = qs.filter(entry__created_on__range=(start_date, end_date))
    else:
        qs = qs.filter(entry__pub_date__range=(start_date, end_date))

    if industryfeed_id == 'yes':
        available_industry_ids = PenseiveIndustry.objects.filter(
            acitve=True
        ).values_list('id', flat=True)
        qs = qs.filter(entry__penseive_industry__id__in=available_industry_ids)
    elif industryfeed_id == 'no':
        qs = qs.filter(entry__penseive_industry__isnull=True)
    elif not industryfeed_id == '':
        industry_ids = IndustryFeed.objects.get(
            id=industryfeed_id
        ).industries.values_list('id', flat=True)
        qs = qs.filter(entry__penseive_industry__id__in=industry_ids)
    else:
        pass
    tq_item_ids = list(set([item.id for item in qs]))
    tq_items = TransmissionQItem.objects.filter(id__in=tq_item_ids)
    tq_items = tq_items.values(
        'publication__account__title', 'publication__title', 'publication__slug'
    ).annotate(c=Count('action')).order_by('publication__account__title', 'publication__title')

    # let us get the total count to be displayed!
    for i in tq_items:
        count = count + i['c']

    return object_list(
        request,
        queryset=tq_items,
        template_name='q/tx_q/status.html',
        template_object_name='qitems',
        extra_context={
            'tx_q': tx_q, 'form': form, 'action': action,
            'action_count': count,
        },
    )


@login_required
@cache_control(private=True)
def tx_q_status_widget(request, year, month, action='T', slug="all"):
    # the following two queries need to be cached!!
    # lets get the valid list of user publications
    try:
        publications = Publication.objects.user_publications(
            request.user).only('title', 'slug')
    except Exception as e:
        logger.info('DashboardError: {}'.format(e))
        return HttpResponse("Something went wrong! Will be fixed soon.")

    try:
        # get the id list, this will be used to identify tx_q columns
        tx_qs = TransmissionQ.objects.user_tx_qs(request.user)
        c = RequestContext(request, {
            'tx_qs': tx_qs, 'year': year, 'month': month, 'action': action,
        })

        template_name = "q/tx_q/status_widget.html"
        t = loader.get_template(template_name)
        response = HttpResponse(t.render(c))
        return response
    except Exception as e:
        logger.info('DashboardError: {}'.format(e))
        return HttpResponse("Something went wrong! Will be fixed soon.")


@login_required
@cache_control(private=True, max_age=getattr(settings, 'CACHE_EXPIRES', 15 * 60))
def tx_q_status_json(request, year, month, action):
    """
    View to display the status of Entries transmitted for a given set of publications
    @action: default value set to 'T', transmitted
    """
    # set the values to fetch
    now = ContifyDateUtil(
        datetime.datetime.strptime('%s, %s' % (month, year), '%b, %Y'))
    start_date, end_date = now.month()
    action = action

    # the following two queries need to be cached!!
    # lets get the valid list of user publications
    publications = Publication.objects.user_publications(request.user).only('title', 'slug')

    # get the id list, this will be used to identify tx_q columns
    tx_qs = TransmissionQ.objects.user_tx_qs(request.user)
    tx_qs_id_list = list(tx_qs.values_list('id', flat=True))
    tx_qs_title_list = list(tx_qs.values_list('title', flat=True))

    # let us prepare the query!
    if request.user.id == 247:
        start_date = start_date - timedelta(days=764)
        qs = TransmissionQItem.objects.filter(
            created_on__range=(start_date, end_date),
            action=action,
            publication__in=publications)
    else:
        qs = TransmissionQItem.objects.filter(
            created_on__range=(start_date, end_date),
            action=action,
            publication__in=publications)

    qs = qs.values('tx_q', 'publication', 'publication__title', 'publication__slug'). \
        annotate(c=Count('action')).order_by('publication')

    # lets re-group results by publications
    pub_list = []
    for key, items in itertools.groupby(qs, operator.itemgetter('publication')):
        pub_list.append(list(items))

    # we want eveyrthing in a nice tabular format, let us define the dictionary
    # to store our results
    userdata = {'Publication': 'Totals'}
    for k in tx_qs_title_list:
        userdata[k] = 0

    results = {
        'records': len(pub_list),
        'page': 1,
        'total': 1,
        'rows': [],
        'userdata': userdata,
    }
    rows = []
    for i in pub_list:
        row = {
            'id': i[0]['publication'],
            'cell':
                [i[0]['publication'],
                 """<a href='%s'>%s</a>""" % (
                     reverse('publications.views.pub_list', args=[i[0]['publication__slug']]),
                     i[0]['publication__title']),
                 ] + [0 for tmp in range(len(tx_qs_id_list))],
        }
        # add transmission q counts
        for j in i:
            try:
                row['cell'][tx_qs_id_list.index(j['tx_q']) + 2] = j['c']
            except ValueError, e:
                continue
            results['userdata'][tx_qs_title_list[tx_qs_id_list.index(j['tx_q'])]] = results['userdata'][
                                                                                        tx_qs_title_list[
                                                                                            tx_qs_id_list.index(
                                                                                                j['tx_q'])]] + j['c']
        results['rows'].append(row)

    json = simplejson.dumps(results)
    return HttpResponse(json, mimetype='application/json')


@login_required
def scheduler(request):
    """
    this view schedules the TransmissionQItems related to a particular TransmissionQ
    """
    publication = ''
    action = ''
    start, end = ContifyDateUtil().today()
    created_on = ''
    tx_q = None
    date_field = 'pub_date'
    updated_count = None
    industryfeed_id = ''
    if request.method == 'POST':
        form = SchedulerForm(request.POST)
        if form.is_valid():
            action = form.cleaned_data['action']
            start = form.cleaned_data['start_date']
            end = form.cleaned_data['end_date']
            tx_q = form.cleaned_data['transmissionq_choice']
            industryfeed_id = form.cleaned_data['industryfeed']
            publication = form.cleaned_data['publication_choice']

        if 'Get_Entries' in request.POST:
            qs = TransmissionQItem.objects.all().select_related()
            if publication:
                qs = qs.filter(publication__id=publication)
            if action:
                qs = qs.filter(action=action)
            if tx_q:
                qs = qs.filter(tx_q=tx_q)
            startDate = datetime.datetime.combine(start, datetime.datetime.min.time())
            endDate = datetime.datetime.combine(end, datetime.datetime.max.time())
            if industryfeed_id:
                industry_ids = IndustryFeed.objects.get(
                    id=industryfeed_id
                ).industries.values_list('id', flat=True)
                qs = qs.filter(entry__penseive_industry__id__in=industry_ids)
            qs = qs.filter(entry__pub_date__gte=startDate, entry__pub_date__lte=endDate)
            queryset = qs.values("tx_q__title", "action").annotate(c=Count('tx_q__title')).order_by()
            return object_list(
                request,
                queryset=queryset,
                template_name='q/tx_q/scheduler.html',
                extra_context={
                    'form': form,
                    'results': queryset,
                    'updated_count': updated_count,
                    'grand_count': 0,
                    'title': 'TransmissionQItems Scheduler',
                    'action_dict': {
                        'T': 'Transmitted',
                        'S': 'Scheduled',
                        'C': 'Created',
                        'F': 'Failed',
                    },
                }
            )

        elif 'Schedule_Entries' in request.POST:
            startDate = datetime.datetime.combine(start, datetime.datetime.min.time())
            endDate = datetime.datetime.combine(end, datetime.datetime.max.time())
            qs = TransmissionQItem.objects.all().select_related()
            if publication:
                qs = qs.filter(publication__id=publication)
            if action:
                qs = qs.filter(action=action)
            if tx_q:
                qs = qs.filter(tx_q=tx_q)
            if industryfeed_id:
                qs = qs.filter(tx_q__industry_feeds__id=industryfeed_id)
            qs = qs.filter(entry__pub_date__gte=startDate, entry__pub_date__lte=endDate)
            updated_count = qs.update(action='S')

            return object_list(
                request,
                queryset=qs,
                template_name='q/tx_q/scheduler.html',
                extra_context={
                    'form': form,
                    'updated_count': updated_count,
                    'title': 'TransmissionQItems Scheduler',
                },
            )

    else:
        form = SchedulerForm({
            'start_date': datetime.date(start.year, start.month, start.day),
            'end_date': datetime.date(end.year, end.month, end.day),
            'tx_q': '',
        })
        return direct_to_template(
            request,
            template='q/tx_q/scheduler.html',
            extra_context={
                'form': form,
                'entry_list': 'entry_list',
                'title': 'TransmissionQItems Scheduler',
                'action_dict': {
                    'T': 'Transmitted',
                    'S': 'Scheduled',
                    'C': 'Created',
                    'F': 'Failed',
                },
            }
        )


def transmitted_count_per_publication(request):
    form = DateBaseReportForm(request.GET)
    if form.is_valid():
        tx_q = form.cleaned_data['transmissionq_choice']
    d = datetime.datetime.now()
    start_date = datetime.datetime.strptime(
        request.GET['start'], "%Y-%m-%d").replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    end_date = datetime.datetime.strptime(
        request.GET['end'], "%Y-%m-%d").replace(
        hour=23, minute=59, second=59
    )
    if not (start_date and end_date):
        end_date = d
        start_date = (d - datetime.timedelta(days=30)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    totalDays = (end_date - start_date).days + 1
    created_on_start_range = d - datetime.timedelta(days=90)
    t = TransmissionQ.objects.get(id=tx_q)
    tq = t.sub_publications.values_list('id', flat=True)
    pqs = Publication.objects.filter(id__in=tq, active=True)
    dayList = [
        (start_date + datetime.timedelta(days=day)) for day in range(totalDays)
    ]
    dataList = []
    headerRow = ["Publication Title"]
    headerRow.extend([item.strftime("%d-%m-%Y") for item in dayList])
    dataList.append(headerRow)
    currentDate = start_date
    for p in pqs:
        rowList = []
        rowList.append(p)
        for currentDate in dayList:
            q = TransmissionQItem.objects.filter(
                publication__id=p.id, tx_q__id=t.id, created_on__year=currentDate.year,
                created_on__month=currentDate.month, created_on__day=currentDate.day, action__exact='T'
            ).count()
            rowList.append(q)
        dataList.append(rowList)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="transmittedcountperpublication.csv"'
    c = csv.writer(response)
    c.writerows(dataList)
    return response