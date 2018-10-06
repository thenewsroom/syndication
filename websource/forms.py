import re

from django import forms
from django.utils.safestring import mark_safe
from django.forms.utils import ErrorList

from .models import Source, SourceUrl

CHECKED_CHOICES = (
       ('all', 'All'),
       ('yes', 'Yes'),
       ('no', 'No')
   )


class SourceStatusForm(forms.Form):
    source = forms.ModelChoiceField(
       queryset=Source.objects.filter(
              account__slug__exact="contify", is_integrated=True
              ).order_by('name'),
       widget=forms.Select, required=False, empty_label='All'
       )
    is_checked = forms.ChoiceField(choices=CHECKED_CHOICES)
    
    
class WebsourceAdminForm(forms.ModelForm):
       
    class Meta:
        model = SourceUrl
        fields = "__all__"

    def clean(self):
        super(WebsourceAdminForm, self).clean()
        cleaned_data = self.cleaned_data
        tag_name = cleaned_data.get('tag_name')
        tag_attr = cleaned_data.get('tag_attr')
        tag_attr_value = cleaned_data.get('tag_attr_value')
        if tag_name == 'a' and tag_attr == 'href':
              try:
                  search_pattern = re.compile(tag_attr_value)
              except Exception:
                    self._errors['tag_attr_value'] = ErrorList(
                     [mark_safe("Please enter a valid search pattern")]
                     )
        return cleaned_data
       
       
class UploadURLForm(forms.Form):
       file  = forms.FileField()                          