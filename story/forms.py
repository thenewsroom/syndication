import urlparse
from datetime import datetime

from django import forms
from django.utils.safestring import mark_safe
from django.forms.utils import ErrorList
from django.template.defaultfilters import slugify
from django.contrib.auth.models import User
from django.contrib.admin import widgets

from .models import Story
from websource.models import Source
#from websource.models import *


CHOICE_STATUS = (
    ('', 'All'),
    ( 1, 'Pending review'),
    ( 0, 'Draft'),
    (-1, 'Rejected'),
    ( 2, 'Published'),
)


class StoryAdminForm(forms.ModelForm):
    """
    1: customization in story admin form to use admin's Radioselect widgets.
    2: Added custom validation for duplicate URL
    """
    class Meta:
        model = Story
        fields = "__all__"
        widgets = {'status': forms.RadioSelect}

    def clean(self):
        """
        To validate story URL
        """
        super(StoryAdminForm, self).clean()
        cleaned_data = self.cleaned_data
        url = cleaned_data.get('url')
        if url:
            parsedURL = urlparse.urlparse(url)
            matchStr = parsedURL.path
            if parsedURL.query:
                matchStr += "?%s" % (parsedURL.query)
            if parsedURL.fragment:
                matchStr += "#%s" % (parsedURL.fragment)
            isDuplicate = False
            # check for duplicate slug
            title = cleaned_data.get('title')
            slug = cleaned_data.get('slug')
            if not slug:
                slug = slugify(title)
            storyQs = Story.objects.only('id', 'slug').filter(slug=slug)
            if self.instance:
                storyQs = storyQs.exclude(id=self.instance.id)
            if storyQs:
                isDuplicate = True
                self._errors['title'] = ErrorList([mark_safe("""<p><a href="/admin/story/story/%d/" target="_blank">Potential Duplicate: story with same title already exists.</a></p>""" % (
                    storyQs.values_list('id', flat=True)[0]))])
            if isDuplicate is False:
                # check for duplicate url
                storyQs = Story.objects.only('id', 'url').filter(url__contains=matchStr)
                if self.instance:
                    storyQs = storyQs.exclude(id=self.instance.id)
                for sobj in storyQs:
                    if urlparse.urlparse(sobj.url).path == matchStr:
                        storyQs = Story.objects.only('id', 'url').filter(id=sobj.id)
                        break
                if storyQs.exists():
                    self._errors['url'] = ErrorList([mark_safe("""<p><a href="/admin/story/story/%d/" target="_blank">Potential Duplicate: story with same URL already exists.</a></p>""" % (
                        storyQs.values_list('id', flat=True)[0]))])
        pub_date = cleaned_data.get('pub_date')
        d = datetime.now().replace(hour=23,minute=59,second=59, microsecond=0)
        if pub_date:
            if pub_date > d:
                self._errors['pub_date'] = ErrorList([mark_safe("Pubdate can't be future date")])
        return cleaned_data


class UserMonitorForm(forms.Form):
    status_field = forms.ChoiceField(
        label = "Status", choices = CHOICE_STATUS, initial='', required=False)

    sources = Source.objects.filter(account__slug='contify').exclude(id__in=[302, 303])

    source_field = forms.ChoiceField(
        [('','All')]+[(u.id, u.name) for u in sources],
        label = "Source", required=False, initial='')

    users_qs = User.objects.filter(is_active=True)

    created_by = forms.ChoiceField(
        [('','All')]+[(u.id, u.username) for u in users_qs],
        label = "Created By", required=False, initial='')

    approved_by = forms.ChoiceField(
        [('','All')]+[(u.id, u.username) for u in users_qs],
        label = "Approved By", required=False, initial='')

    date_field = forms.ChoiceField(choices=[
        ('updated_on','Updated on'),
        ('approved_on', 'Approved on'),
        ('created_on', 'Created on'),
    ], label="Select date", required=False,)

    start_day = forms.SplitDateTimeField(required=False,
                                     widget=widgets.AdminSplitDateTime())
    end_day = forms.SplitDateTimeField(required=False,
                                   widget=widgets.AdminSplitDateTime())
