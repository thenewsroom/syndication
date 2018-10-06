"""
Base class used to extract entity information from third party apps
and store them in the database
"""

import copy
import logging

from django.contrib.contenttypes.models import ContentType

from penseive.models import (
    PenseiveItem, EntityItem, Entity, EntityType, QuoteItem
)
from penseive.exceptions import NotImplementedError

logger = logging.getLogger(__name__)


class Penseive(object):
    """
    """
    
    def __init__(self, content_object):
        self.content_object = content_object
        self.content_type = ContentType.objects.get_for_model(content_object)
        self.source = self.get_source()
        
        self.results = None # the results of analysis
        
        self.entity_defaults = {
            'type': {'name': '', 'source': self.source,
                     'defaults': {'active': True, 'scope_note':None},},
            'entity':{'name': '', 
                      'defaults': {'active': True,
                                   'status': 'P',
                                   'attributes': '',
                                   'display_name':None,
                                   'same_as':None,
                                   'parent': None,
                                   'source': self.source,
                                   'scope_note':None},},
            'relevance': 0, 'active': True,
        }
        
        self.quote_defaults = {
            'quote': '',
            'entity':{'name': None},
            'potential_match':{'name': None},
        }
        
        self.entities = []  # list of entities
        self.quotes = []  # list of quotes
    
    def get_default_entity(self):
        return copy.deepcopy(self.entity_defaults)
    
    def get_default_quote(self):
        return copy.deepcopy(self.quote_defaults)
    
    def get_source(self):
        """
        define the source for the tags
        """
        raise NotImplementedError('Missing module:: get_source')
    
    def analyze(self, content, content_type):
        """
        analyze the data, to be implemented in the third party app api
        
        it must return raw / simplified results in json format
        """
        raise NotImplementedError('Missing module:: analyze')
    
    def check_penseive_exists(self, pitem):
        """
        check if the entities for the given penseive item exists in the db
        """
        raise NotImplementedError('Missing module:: check_penseive_exists')
    
    def extract_entities(self):
        """
        populate the entities, to be implemented in the third party app api
        each entity must follow the self.entity_defaults structure defined in __init__
        {
            'type': {'name': '', 'urlhash': '', 'source': ''},
            'entity':{'name': '', 'urlhash': '', 'defaults': {'attributes': ''},},
            'relevance': 0, 'active': True,
        }
        
        it must return a list of entities
        """
        raise NotImplementedError('Missing module:: extract_entities')
        
    def extract_quotes(self):
        """
        populate the  quotes, to be implemented in the third party app api
        it must return a list of quotes
        """
        raise NotImplementedError('Missing module:: extract_quotes')
        
        
    def check_penseive_quote_exists(self, pitem):
        """
        check if the quotes for the given penseive item exists in the db
        """
        raise NotImplementedError('Missing module:: check_penseive_quote_exists')

    def update_penseive(self):
        # check if entities for the given object already exist in the penseive
        pitem, created = PenseiveItem.objects.get_or_create(
            content_type=self.content_type, object_id=self.content_object.pk
        )
        
        if not created and self.check_penseive_exists(pitem):
            logger.debug('Calais entities exist for penseive item: %s, nothing to do' % pitem)
        else:
            logger.debug('Refresh Calais entities for penseive item: %s' % pitem)
            if not self.entities:
                self.extract_entities()
                
            # create new relationship with entities
            for item in self.entities:
                type, ct = EntityType.objects.get_or_create(**item['type'])
                
                # add type to entity dict
                item['entity']['type'] = type
                entity, ec = Entity.objects.get_or_create(**item['entity'])
                
                # Note: the item active flag should be based on type's and entity's active flag
                # first time when type or entity is created, it will always be active
                # user can change the default setting via admin screen
                # for subsequent additions:
                # if a type is inactive, item will be inactive
                # if a type is active but entity is inactive - mark the item as inactive
                # this can be manually changed by the user later using admin screen                
                item_active_flag = True
                if not type.active or (type.active and not entity.active):
                    item_active_flag = False
                # Note: this cannot be done at entity_item.save() as the user
                # has full permissions to make any entity item active / inactive
                    
                entity_item = EntityItem.objects.get_or_create(
                    penseive_item=pitem, entity=entity, relevance=item['relevance'],
                    defaults={'active': item_active_flag }
                )
        
        if not created and self.check_penseive_quote_exists(pitem):
            logger.debug('Calais quotes exist for penseive item: %s, nothing to do' % pitem)
        else:
            logger.debug('Refresh Calais quotes for penseive item: %s' % pitem)
            if not self.quotes:
                self.extract_quotes()
                
            # create new quote relationship with entitiy i.e. name
            
            for r in self.quotes:
                # when the quote is created first time it is always active
                # this can be changed manually through admin screen
                quote_item, qt = QuoteItem.objects.get_or_create(quote_text=r['quote'],
                penseive_item=pitem, entity=r['entity']['name'], potential_match=r['potential_match']['name'],
                active=True)