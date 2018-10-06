"""
Integrate Open Calais with the Peseive
Uses calais.py to fetch the tags and extract meanigful information from it
"""
import logging
import time

from django.conf import settings
from django.db.models.fields import FieldDoesNotExist
from django.utils.safestring import mark_safe

from calais import Calais
from cutils.utils import escape_text, unicode_to_ascii, pre_process_data
from penseive import base
from penseive.exceptions import OpenCalaisTagFetchError
from penseive.models import Entity, EntityType

logger = logging.getLogger(__name__)

# the raw data is saved in the attributes field, we will store all attributes
# except for those listed below
ATTRIBUTE_EXCLUDE_LIST = [
    # we are already storing this information in database
    '_type', 'name', 'relevance', 'score', 'categoryName', 'importance',
    # all this is not required, can be ignored
    'instances', '_typeReference', '__reference'
    ]

class OpenCalais(base.Penseive):
    """
    OpenCalais integration with Penseive. To use this with one of the models
    you need to define the following calais_content_fields in the calling model
    
    Usage:
    Refer to cms/penseive_entities.py

    """
    
    def __init__(self, content_object, content_fields=None):
        super(OpenCalais, self).__init__(content_object)
        self.calais = Calais(settings.CALAIS_API_KEY, settings.CALAIS_SUBMITTER)
        
        if content_fields:
            self.calais_content_fields = content_fields
        else:
            try:
                self.calais_content_fields = dict(
                    self.content_object.__class__.calais_content_fields)
            except FieldDoesNotExist, e:
                raise OpenCalaisTagFetchError(
                    'You need to define calais_content_fields: %s' % e)                

    
    def set_processing_directives(self):
        """fetch social tags and generic relations also"""
        self.calais.processing_directives['enableMetadataType'] = "GenericRelations,SocialTags"
        
    def get_source(self):
        return 'C'
    
    def _prepare_calais_xml(self, title, body, pubdate):
        return '<root><TITLE>%s</TITLE><BODY>%s</BODY><PUBDATE>%s</PUBDATE></root>' % (
            mark_safe(unicode_to_ascii(escape_text(pre_process_data(title, remove_tags='all')))),
            mark_safe(unicode_to_ascii(escape_text(pre_process_data(body, remove_tags='all')))),
            pubdate.strftime("%Y-%m-%d"),
        )
    
    def _prepare_calais_html(self, title, body, pubdate):
        return '<h1>%s</h1><p>%s</p><p>%s</p>' % (
            mark_safe(unicode_to_ascii(escape_text(pre_process_data(title)))),
            mark_safe(unicode_to_ascii(escape_text(pre_process_data(body)))),
            pubdate.strftime("%Y-%m-%d"),
        )
    
    def get_content(self, format="HTML"):
        """
        Fetches the content from the object. The calais_content_fields must
        be defined in the penseive_entities file for the model
        it must have
        TITLE (char / text field), BODY (char / text field) and PUBDATE (datetime)
        eg:
        calais_content_fields = [
            ('TITLE', 'title'), ('BODY', 'body_html'), ('PUBDATE', 'pub_date')
        ]
        
        You can refer to: http://www.b-list.org/weblog/2007/nov/04/working-models/
        to learn more on how to pull important information from model meta
        """
        # check if the obj has calais_content_fields defined
        opts = self.content_object._meta
        fields = self.calais_content_fields
        
        try:
            title = getattr(self.content_object, fields['TITLE'])
            body = getattr(self.content_object, fields['BODY'])
            pubdate = getattr(self.content_object, fields['PUBDATE'])
        except AttributeError, e:
            raise OpenCalaisTagFetchError(
                'Invalid calais_content_fields, please fix: %s' %e)
        
        if format == "HTML":
            return self._prepare_calais_html(title, body, pubdate)
        else:
            return self._prepare_calais_xml(title, body, pubdate)
    
    def analyze(self, content=None, content_type='TEXT/HTML'):
        """
        content and the type need to be pulled from the object definition
        """
        self.set_processing_directives()
        
        # if content is not defined, see if the calais_content_fields is defined
        if not content:
            content = self.get_content(format="HTML")
            # you get better results with text/html instead of text/xml
            # not sure why ... 
            content_type = 'TEXT/HTML'
        
        # lets get to business - fetch the tags
        try:
            results = self.calais.analyze(
                content, content_type=content_type,
                external_id=u'%s' % self.content_object.pk)
        except IOError, e:
            if hasattr(e, 'reason'):
                logger.error('Calais Error when analyzing %s, Reason: %s' % (
                    self.content_object, e.reason))
            raise OpenCalaisTagFetchError(
                'Error communicating with Calais server, unable to analyze: %s. \
                    Error: %s' % (self.content_object, e))
        except Exception, e:
            raise OpenCalaisTagFetchError(
                'Unknown Calais error, unable to analyze: %s. Error: %s' % (
                    self.content_object, e))
        
        # do a quick sanity check:
        if not results.doc['meta']['language'] == 'English':
            raise OpenCalaisTagFetchError(
                'We only support English language, found: %s' \
                    % results.doc['meta']['language'])
        
        # all looks good
        logger.debug('Calais successfully analyzed: %s' % self.content_object)
        self.results = results.simplified_response

    def check_penseive_exists(self, pitem):
        """returns True if calais entities exist for the penseive item p"""
        calais_entities = pitem.entityitem_set.all().filter(type__source='C')
        if calais_entities.count() > 0:
            return True
        return False
        
        
    def check_penseive_quote_exists(self, pitem):
        """returns True if calais quotes exist for the penseive item p"""
        calais_quotes = pitem.quoteitem_set.all().filter(entity__type__source='C')
        if calais_quotes.count() > 0:
            return True
        return False
        
    def extract_social_tags(self):
        """
        extracts the social tags from Calais response and stores them as an
        entity of type "Tag" in the system
        """
        social_tags = []
        if self.results.has_key('socialTag'):
            for r in self.results['socialTag']:
                # initialize
                social_tag = self.get_default_entity()
                social_tag['type']['name'] = 'Tag'
                
                # populate and add to the list
                social_tag['entity']['name'] = r['name']
                social_tag['relevance'] = r['importance']
                social_tags.append(social_tag)
        else:
            logger.error('No Social Tag found for object: %s' %(self.content_object))
        return social_tags
    
    def extract_topics(self):
        """
        extracts the Topic information from Calais response and stores them
        as an entity of type "Category" in the system
        """
        topics = []
        if self.results.has_key('topics'):
            for r in self.results['topics']:
                # initialize
                topic = self.get_default_entity()
                topic['type']['name'] = 'Category'
                
                # populate and add to list
                topic['entity']['name'] = r['categoryName']
                if r.has_key('relevance'):
                    topic['relevance'] = r['score']
                    
                topics.append(topic)
        else:
            logger.error('No topic found for object: %s' %(self.content_object))
        return topics
    
    def extract_entities(self):
        """
        extracts all the entities from the Calais response, appends the social
        tags and topics fetched to the list
        """
        # check if the results have been populated
        if not self.results:
            try:
                self.analyze()
            except OpenCalaisTagFetchError, e:
                # try once again ...
                time.sleep(30)
                self.analyze()
                    
        self.entities = []

        # extract the entities now ... make sure entities exist first!        
        if self.results.has_key('entities'):
            for r in self.results['entities']:
                # initialize
                entity = self.get_default_entity()
                entity['type']['name'] = r['_type']
                entity['entity']['name'] = r['name']
                entity['relevance'] = r['relevance']
                
                # clean information that we dont need - they will take way too
                # much space and can be ignored for now  and stored in PickledObjectField
                attribute = {}
                for k,v in r.items():
                    if not k in ATTRIBUTE_EXCLUDE_LIST:
                        attribute[k] = v
                entity['entity']['defaults']['attributes'] = attribute
                self.entities.append(entity)
            
        self.entities = self.entities + self.extract_social_tags() + self.extract_topics()
        return self.entities
    
    def extract_quotes(self):
        """
        extracts all the quotes and name of the entity i.e. person
        from the Calais response
        """
        
        # check if the results have been populated
        if not self.results:
            try:
                self.analyze()
            except OpenCalaisTagFetchError, e:
                # try once again ...
                time.sleep(30)
                self.analyze()
        
        self.quotes = []
        
        # extract the quotes and entity name i.e. person now ... make sure quotes exist first!
        if self.results.has_key('relations'):
            for r in self.results['relations']:
                quote = self.get_default_quote()
                    
                # get only the quotes from the calais response
                if r['_type'] == 'Quotation':
                    quote['quote'] = r['quote']
                    person = EntityType.objects.get(name__exact='Person')
                    try:
                        en, ne  = Entity.objects.get_or_create(name__exact=r['person']['name'], type=person)
                        if ne:
                            en.name = r['person']['name']
                            en.save()
                        quote['entity']['name'] = en
                    except TypeError:
                        hash = r['person']
                            
                        for i in self.results['entities']:
                            if i['__reference'] == hash:
                                en, ne  = Entity.objects.get_or_create(name__exact=i['name'], type=person)
                                if ne:
                                    en.name = i['name']
                                    en.save()
                                quote['potential_match']['name'] = en
                    self.quotes.append(quote)
                        
        return self.quotes