from penseive.exceptions import AlreadyRegistered, NotRegistered
from penseive.entities import PenseiveEntities

class PenseiveSite(object):
    """
    Inspired by django admin and haystack
    
    A PenseiveSite instance should be instantiated in your URLconf
    
    The API intentionally follows that of django.contrib.admin's AdminSite as
    much as it makes sense to do.
    """
    
    def __init__(self):
        self._registry = {}    

    def register(self, model, entity_class=None):
        """
        Registers a model with the site.
        If already registered, this will raise AlreadyRegistered.
        """
        if model in self._registry:
            raise AlreadyRegistered('The model %s is already registered' % model)
        
        if not entity_class:
            from penseive.entities import PenseiveEntities
            entity_class = PenseiveEntities
        self._registry[model] = entity_class(model)
        self._setup(model, self._registry[model])
        
    def unregister(self, model):
        """
        Unregisters a model from the site.
        """
        if model not in self._registry:
            raise NotRegistered('The model %s is not registered' % model)
        del(self._registry[model])
        
    def get_penseive(self, model):
        try:
            return self._registry[model]
        except KeyError:
            raise Exception("Unregistered model: '%s'" % model)        
        
    def _setup(self, model, penseive_entity):
        penseive_entity._setup_save(model)
        penseive_entity._setup_delete(model)

    def _teardown(self, model, penseive_entity):
        penseive_entity._teardown_save(model)
        penseive_entity._teardown_delete(model)
        
site = PenseiveSite()