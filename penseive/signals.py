import logging

import django.dispatch
from django.db.models.signals import post_save

from cms.models import Entry, IndexingQueue
from penseive.models import Entity, EntityItem

# define signals
updated_entityitem_active_flag = django.dispatch.Signal(
                                    providing_args = ["entity", "active"])


def update_indexing_queue(objects=[]):
    """
    Entry objects need to be added to the indexing queue
    """
    # avoid duplicates in objects
    count = 0
    for obj in list(set(objects)):
        try:
            entry = Entry.objects.get(id=obj)
            ixq, created = IndexingQueue.objects.get_or_create(entry=entry)
            if created:
                count += 1
        except:
            # looks like Entry with this id does not exist - most likely deleted
            # or most likely the object is not of type Entry!
            logging.error("Unable to update_indexing_queue, unable to find Entry id: %d" % obj)
    
    logging.debug('%d Entry object/s added to indexing queue' % count)

def entity_postsave_handler(sender, **kwargs):
    """
    Post save handler for the Entity
    Each time an Entity is updated, correponding Entries need to be refreshed
    """
    entity = kwargs['instance']
    
    # fetch all entries associated with this entity and reindex them
    entries = EntityItem.objects.filter(entity=entity).values_list('penseive_item__object_id', flat=True)
    update_indexing_queue(entries)

def entityitem_postsave_handler(sender, **kwargs):
    """
    Post save handler for the EntityItem
    
    Each time an EntityItem is updated, correponding Entry need to be refreshed
    
    This will cause duplicated items to be added to Indexing Queue - each time
    an Entity is saved ... need to see how to restrict calling this function
    only if the EntityItem is being saved manually - most likely a signal needs
    to be trigered from the admin screen
    """
    entityitem = kwargs['instance']
    
    # fetch all entries associated with this entity and reindex them
    update_indexing_queue([entityitem.penseive_item.object_id])

def update_entityitem_active_flag(sender, **kwargs):
    """
    update handler for EntityItem
    Known Issue: No Content Type check added to EntityItem - assuming everything
    is an Entry object
    """
    # fetch parameters
    entity = kwargs['entity']
    active = kwargs['active']
    
    # fetch all EntityItems that belong to this entity that do not have the
    # new active flag
    from penseive.models import Entity, EntityItem

    qs = EntityItem.objects.filter(entity=entity).exclude(active=active)
    #objects_tobe_indexed = []
    update_count = 0
    for i in qs.iterator():
        i.active=active
        
        # we could have done a simple qs.update(active=active)
        # but we need to force the validation and threshold logic
        # to be applied to the active flag - hence do a save() on each item
        i.save()
        update_count += 1
        #objects_tobe_indexed.append(i.penseive_item.object_id)
        
    #update_count = qs.update(active=active)
    logging.debug("Active flags updated to %s for %d EntityItems corresponding to Entity: %s" %(active, update_count, entity))
    
    #objects_tobe_indexed = qs.values_list('penseive_item__object_id', flat=True)
    #update_indexing_queue(objects_tobe_indexed)
    
# listed to all signals
post_save.connect(entity_postsave_handler, sender=Entity)    
post_save.connect(entityitem_postsave_handler, sender=EntityItem)

# listen to the update entityitem signal!!
# as of now the signal is triggered from penseive.models each time an Entity's
# status gets updated
updated_entityitem_active_flag.connect(update_entityitem_active_flag)
