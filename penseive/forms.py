from django import forms
from penseive.models import EntityItem

class EntityItemForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(EntityItemForm, self).__init__(*args, **kwargs)
        instance = getattr(self, 'instance', None)
        if instance and instance.id:
            self.fields['active'].label = '%s' % (instance.entity.name)
            
    class Meta:
        model = EntityItem
        exclude = ('type', 'penseive_item', 'relevance', 'entity', )

