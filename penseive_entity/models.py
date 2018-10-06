# from django.db import models
#
# # Create your models here.
# from mptt.models import MPTTModel
#
#
# class Industry(MPTTModel):
#     """
#     class to manage the Industry relationships with entry
#     Every object has a name, parent and same_as
#     """
#     name = models.CharField(max_length=255)
#     parent = models.ForeignKey('self', blank=True, null=True, default=None, related_name='child_topic')
#     scope_note = models.TextField(null=True, blank=True)
#     active = models.BooleanField(default=True)
#     # Multiple parents
#     parent_2 = models.IntegerField(null=True, blank=True, help_text='Enter the ID of the Parent 2')
#     parent_3 = models.IntegerField(null=True, blank=True, help_text='Enter the ID of the Parent 3')
#
#     class Meta:
#         verbose_name_plural = 'Industries'
#
#     class MPTTMeta:
#         parent_attr = 'parent'
#         level_attr = 'mptt_level'
#         order_insertion_by = ['name']
#         ordering = ['tree_id', 'lft']
#         verbose_name_plural = 'Industries'
#
#     def __unicode__(self):
#         return self.name
#
#     def getTopLevelIndustry(self):
#         if not self.parent:
#             return self
#         else:
#             self = self.parent
#             return self.getTopLevelIndustry()
#
#     def save(self, *args, **kwargs):
#         self.name = self.name.strip()
#
#         super(Industry, self).save(*args, **kwargs)