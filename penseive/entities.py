# Penseive Base Class
from django.db.models import signals


class PenseiveEntities(object):
    
    def __init__(self, model):
        self.model = model
    
        # list of tuples that need to be indexed by Calasis
        #calais_content_fields = [
        #    ('TITLE', 'title'), ('BODY', 'body_html'), ('PUBDATE', 'pub_date')
        #]
        # self.calais_content_fields = []
        
    def _setup_save(self, model):
        signals.post_save.connect(self.update_object, sender=model)
    
    def _setup_delete(self, model):
        signals.post_delete.connect(self.remove_object, sender=model)

    def _teardown_save(self, model):
        signals.post_save.disconnect(self.update_object, sender=model)
    
    def _teardown_delete(self, model):
        signals.post_delete.disconnect(self.remove_object, sender=model)
        
    def update_opencalais(self, objects):
        from penseive.opencalais import OpenCalais
        for object in objects:
            o = OpenCalais(object, dict(self.calais_content_fields))
            o.update_penseive()
    
    def update_object(self, instance, **kwargs):
        """
        Update the entity information for a single object.
        """
        if self.calais_content_fields:
            self.update_opencalais([instance])

    def remove_object(self, instance, **kwargs):
        """
        If an object is deleted - remove it from penseive
        """
        pass