# Create your views here.
import datetime
from operator import itemgetter
from itertools import groupby

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.shortcuts import render_to_response
from django.template.context import RequestContext
from django.views.decorators.cache import cache_control
from django.views.generic.list_detail import object_list

from cms.models import Entry
from cutils.tagcloud import tagcloud
from cutils.utils import flatten
from penseive import site
from penseive.models import PenseiveItem, Entity, EntityType, EntityItem
from search.query import SearchQuerySet


@cache_control(private=True, max_age=getattr(settings, 'CACHE_DASHBOARD_EXPIRES', 15 * 60))
def details(request, model, object_id):
    # fetch the content type from the model and then the penseive object
    content_type = get_object_or_404(ContentType, model=model)
    p = get_object_or_404(
        PenseiveItem, content_type=content_type, object_id=object_id)

    # get all the entities
    # entities = p.entityitem_set.all().values(
    #    'entity__name', 'type', 'type__name', 'relevance', 'active')
    # data = sorted(entities, key=itemgetter('type__name'))
    #
    # entity_forms = []
    # put the entities in a meaningful structure to be picked up by
    # the template
    results = []
    # for k, g in groupby(data, itemgetter('type__name')):
    #    results.append((k, list(g)))

    return render_to_response('penseive/detail.html',
                              {'results': results, 'model': model, 'object': p, },
                              context_instance=RequestContext(request))


@cache_control(private=True, max_age=getattr(
    settings, 'CACHE_DASHBOARD_EXPIRES', 15 * 60))
def entity(request):
    qs = EntityItem.objects.all().filter(active=True)
    qs = qs.values('type__name').annotate(c=Count('penseive_item')).order_by()

    tagcount = 10
    if request.GET:
        if request.GET.has_key('tagcount'):
            tagcount = int(request.GET.get('tagcount'))
    cloud = tagcloud(list(qs), 'type__name', 'c', tagcount)

    return render_to_response('penseive/entity_cloud.html',
                              {'cloud': cloud, 'title': 'Entity Types', 'link_entity': True},
                              context_instance=RequestContext(request))


@cache_control(max_age=getattr(settings, 'CACHE_DASHBOARD_EXPIRES', 15 * 60))
def entities(request, type):
    """
    displays the entities that belong to the selected type
    the results are fetched from search index by default
    if the querystring indexed_data is set to N, the results will be fetched
    from the database instead of the index
    """
    # make sure that type is valid and exists!
    t = get_object_or_404(EntityType, name=type)

    # each entity to have atleast this many # of stories to appear in the cloud
    tagcount = 25

    # variable to identify if results to be fetched from search or db
    # default set to Y
    indexed_data = "N"

    if request.GET:
        # see if the tagcount is present - get it
        if request.GET.has_key('tagcount'):
            tagcount = int(request.GET.get('tagcount'))

        # see if the sqs is set, get it
        if request.GET.has_key('indexed_data'):
            indexed_data = request.GET.get('indexed_data')

    if indexed_data == 'Y':
        # search for the selected entity type, get the facet counts
        entity = '%s_entity' % type
        sqs = SearchQuerySet().facet(entity)

        cloud = tagcloud(sqs.facet_counts()['fields'][entity], threshold=tagcount)
    else:
        # get results from db
        indexed_data = 'N'
        qs = EntityItem.objects.all().filter(active=True, type=t)

        ## get the name and counts to generate the cloud
        qs = qs.values('entity__name').annotate(c=Count('penseive_item')).order_by()
        cloud = tagcloud(qs, 'entity__name', 'c', tagcount)

    return render_to_response('penseive/entity_cloud.html',
                              {'cloud': cloud, 'title': 'Entities for %s' % (type), 'type': t,
                               'indexed_data': indexed_data},
                              context_instance=RequestContext(request))


@cache_control(max_age=getattr(settings, 'CACHE_DASHBOARD_EXPIRES', 15 * 60))
def entity_list(request, type, name):
    """
    Returns the list of PenseiveItems that belong to "entity"
    By default entries will be fetched from the search index
    If indexed_data is present in the querystring and set to N, results will
    be fetched from the datbase
    """

    # lets make sure the entity exists - first check with name
    # and then with display_name

    entity = Entity.objects.none()
    try:
        entity = Entity.objects.get(type__name=type, name=name)
    except Entity.DoesNotExist:
        try:
            entity = Entity.objects.get(type__name=type, display_name=name)
        except Entity.DoesNotExist:
            # unable to find any entity - raise a 404!
            from django.http import Http404
            raise Http404

    if entity.same_as:
        entity = entity.same_as

    # check if the querystring has indexed_data set, this will define
    # if results to be fetched from search or database
    indexed_data = 'N'
    if request.GET:
        # see if the sqs is set, get it
        if request.GET.has_key('indexed_data'):
            indexed_data = request.GET.get('indexed_data')

    if indexed_data == 'Y':
        # get results from search index
        # The ids are extracted from the sqs return by solr
        entity_type = '%s_entity__in' % str(type)
        val = [str(name)]

        # Add the filter for the entity selected
        sqs = SearchQuerySet().filter(**{entity_type: val})

        # Prepare the list of ids of the articles
        entry_id = []
        for r in sqs:
            entry_id.append(r.pk)

        # lets fetch the entries
        qs = Entry.objects.filter(id__in=entry_id)

    else:
        # fetch data from the database!
        indexed_data = 'N'

        ei = EntityItem.objects.filter(type__name=type).select_related('penseive_item')

        # get EntityItems that are associated with Entity, same_as and have parent as current entity
        ei_all = ei.filter(entity=entity) | ei.filter(entity__same_as=entity)

        obj_list = ei_all.values_list('penseive_item__object_id', flat=True)

        # lets fetch the entries
        qs = Entry.objects.filter(id__in=obj_list)

    # fine tune the query and only get the required fields
    qs = qs.select_related('publication').only(
        'id', 'title', 'slug', 'by_line', 'pub_date', 'body_html',
        'publication__title', 'publication__slug', 'publication__id')

    # display all child entities on the sidebar
    # child_entities = Entity.objects.filter(active=True, parent=entity)
    child_entities = list(flatten(entity.get_all_child_entities()))

    return object_list(
        request,
        queryset=qs,
        paginate_by=settings.PAGINATE_BY_SIZE,
        template_name='penseive/entity_list.html',
        extra_context={
            'entity': entity,
            'child_entities': child_entities,
            'indexed_data': indexed_data,
        }
    )

# we are getting rid of these codes
# def industry_gics_codes_json(request, parent_id=1):
#    results = []
#
#    if request.GET:
#        try:
#            if request.GET.has_key('sector'):
#                parent_id = int(request.GET.get('sector'))
#            if request.GET.has_key('industry_group'):
#                parent_id = int(request.GET.get('industry_group'))
#                # for industry, user can choose "All" - add it to the options
#                results.append({'id': 0, 'name': u'All'})
#            if request.GET.has_key('industry'):
#                parent_id = int(request.GET.get('industry'))
#        except ValueError:
#            # GET should only have integer values - invalid parent_id passed
#            # set it to 0!
#            parent_id = 0
#
#    qs = Industry.objects.filter(parent__id=parent_id).values('id', 'name')
#    return HttpResponse(simplejson.dumps(results + list(qs)), mimetype='application/javascript')
