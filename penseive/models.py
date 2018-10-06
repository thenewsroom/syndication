from operator import itemgetter
from itertools import groupby

from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.core.urlresolvers import reverse

# Create your models here.

ENTITY_SOURCE = (
    ('C', 'Calais'),
    ('M', 'Manual'),
    ('A', 'Alchemy API'),
)

ENTITY_STATUS = (
    ('A', 'Active'),
    ('P', 'Pending'),
    ('I', 'Inactive'),
)


class Industry(models.Model):
    """
    class to manage the Industry relationships
    Every object has a code and a parent
    """
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=255)
    parent = models.ForeignKey('self', blank=True, null=True, related_name='child_set')

    class Meta:
        ordering = ['code', ]
        verbose_name_plural = 'Industries'

    def __unicode__(self):
        return self.full_name()

    def level(self):
        """
        count the number of parents for this entity
        """
        if not self.parent:
            return 0
        return 1 + self.parent.level()

    def full_name(self):
        if self.parent_id:
            return '%s%s%s' % (self.parent, self.get_separator(), self.name)
        else:
            return self.name

    def get_separator(self):
        return ' :: '

    def is_leaf(self):
        """
        returns True if this entity does not have a child
        """
        if self.child_set.all():
            return False
        return True


class EntityType(models.Model):
    """
    to store Entity Types
    """
    name = models.CharField(max_length=300)
    source = models.CharField(max_length=1, choices=ENTITY_SOURCE, default='M')
    active = models.BooleanField()
    relevance_threshold = models.FloatField(default=0)

    """
    ALTER TABLE penseive_entitytype ADD COLUMN "scope_note" text;    
    """
    scope_note = models.TextField(null=True, blank=True)

    def __unicode__(self):
        return '%s' % (self.name)

    def get_absolute_url(self):
        return reverse('penseive.views.entities', args=[self.name])


class Entity(models.Model):
    """
    class to store the Entity information retrieved from Calais, Alchemy etc
    attributes will be used to store the raw Pickled object that can be
    later used to extract more meaning out of the output

    display_name has been added to alter the name of the entity retrieved
    same_as has been added to indicate that the entity is same_as some other entity
    """
    name = models.CharField(max_length=300, db_index=True)
    type = models.ForeignKey(EntityType)
    active = models.BooleanField(
        help_text="Will be updated by the system to False if status is Inactive, else will remain True")

    """
    ALTER TABLE penseive_entity ADD COLUMN "display_name" varchar(300);
    ALTER TABLE penseive_entity ADD COLUMN "same_as_id" integer;
    CREATE INDEX "penseive_entity_same_as_id" ON "penseive_entity" ("same_as_id");
    """
    display_name = models.CharField(max_length=300, null=True, blank=True)
    same_as = models.ForeignKey('self', null=True, blank=True, db_index=True)

    """
    ALTER TABLE penseive_entity ADD COLUMN "source" varchar(1);
    ALTER TABLE penseive_entity ADD COLUMN "parent_id" integer;
    ALTER TABLE "penseive_entity" ADD CONSTRAINT "parent_id_refs_id_645ff677" FOREIGN KEY ("parent_id") REFERENCES "penseive_entity" ("id") DEFERRABLE INITIALLY DEFERRED;
    CREATE INDEX "penseive_entity_parent_id" ON "penseive_entity" ("parent_id");

    # need to update - if source is empty set to "C"

    ALTER TABLE penseive_entity ADD COLUMN "scope_note" text;
    ALTER TABLE penseive_entity ADD COLUMN "created_on" timestamp with time zone;
    CREATE INDEX "penseive_entity_created_on" ON "penseive_entity" ("created_on");

    """
    source = models.CharField(max_length=1, choices=ENTITY_SOURCE, default='M')
    parent = models.ForeignKey('self', null=True, blank=True, db_index=True, related_name='child_set')

    scope_note = models.TextField(null=True, blank=True,
                                  help_text="If same_as exists for this Entity, the scope_note of the same_as Entity will be displayed at the front end and any value entered here will be ignored")
    created_on = models.DateTimeField(null=True, blank=True, auto_now_add=True, db_index=True)

    """
    ALTER TABLE penseive_entity ADD COLUMN "status" varchar(1);
    CREATE INDEX "penseive_entity_status" ON "penseive_entity" ("status");
    CREATE INDEX "penseive_entity_status_like" ON "penseive_entity" ("status" varchar_pattern_ops);    
    """
    status = models.CharField(max_length=1, choices=ENTITY_STATUS, default='P', null=True, blank=True, db_index=True)

    class Meta:
        verbose_name = 'entity'
        verbose_name_plural = 'entities'

    def __unicode__(self):
        return u'%s' % (self.name)

    def get_display_name(self):
        """
        returns the display_name, if present else returns the name
        """
        if self.display_name:
            return self.display_name
        return self.name

    def get_absolute_url(self):
        return reverse('penseive.views.entity_list',
                       args=[self.type.name, self.name])

    def get_entity_name(self):
        """
        if the object has same_as populated, returns the display_name of the
        same_as object
        """
        if self.same_as and not self.same_as == self:
            return self.same_as.get_entity_name()
        return self.get_display_name()

    def get_entity_type(self):
        """
        child entity inherits the type of the parent
        if entity has same_as, use the same_as type
        else just return the type
        """
        if self.parent and not self.parent == self:
            return self.parent.type
        if self.same_as and not self.same_as == self:
            return self.same_as.type
        return self.type

    def get_scope_note(self):
        """
        if the object has same_as populated, returns the scope_note of the
        same_as object
        """
        if self.same_as:
            return self.same_as.scope_note
        return self.scope_note

    def is_sameas_parent_entity(self):
        """parent entity is the one that has same_as either None or itself"""

        if not self.active:
            return False
        if not self.same_as:
            return True
        if self.same_as.id == self.id:
            return True
        return False

    def get_active_status(self):
        """
        Returns the Entity status based on the status field and the active flag

        Entity will be inactive only if its status is set to I
        in all other cases it should be considered as active

        For existing entities, status field will be Null, the active flag will
        be used to determine the current status
        """
        if not self.status:
            # for existing Entities which have status set to Null
            return self.active
        elif self.status == "I" or not self.type.active:
            # for cases when status is set to Inactive or
            # if the Type is inactive - entity should by default be
            # marked as inactive
            return False
        else:
            # for cases when status is Active or Pending
            return True

    def get_child_entities(self):
        """
        returns the child entities, if they exist
        entities who have their parent set to self
        """
        return Entity.objects.filter(parent=self)

    def get_all_child_entities(self):
        """
        returns tuple of parent, child entities across all hierarchies
        eg if we have the following parent - child hierarchy
        369177
         |--369176
         |    |--411767
         |    |--420643
         |--411763
         |--420648

        e.get_all_child_entities() where e=369177 will return
        [(369176, [(411767, []), (420643, [])]), (411763, []), (420648, [])]

        to flatten the results you can use cutil.utils.flatten(lst)
        list(flatten(e.get_all_child_entities())) will return
        [369176, 411767, 420643, 411763, 420648]

        Note the example above shows ids, they will be replaced by the actual
        Entity object
        """
        result = []
        for i in self.get_child_entities():
            result.append((i, i.get_all_child_entities()))
        return result

    def get_sameas_child_entities(self):
        """
        if the entity is a parent, this will fetch all the child entities
        associated with it!
        if entity is a child entity, it cannot be the same_as for any other entity
        possible that a parent is being changed to a child and it is still
        being refrenced!
        """
        qs = Entity.objects.none()
        if self.id:
            # qs = Entity.objects.filter(type=self.type, same_as__id=self.id)
            qs = Entity.objects.filter(same_as__id=self.id)

            # ignore the current entity
            qs = qs.exclude(id=self.id)

        return qs

    def validate_display_name(self, display_name):
        """
        only parent entities can have display_name
        """
        if display_name and not self.is_sameas_parent_entity():
            return False
        return True

    def validate_same_as(self, same_as):
        """
        if same_as exists, ensures that it is valid
        """
        if same_as:
            try:
                # 1. check if the same_as.id exists and belongs to the same type
                # remove the type check - just chekc the active flag
                same_as = Entity.objects.get(
                    id=same_as.id, active=True)

                # 2. same_as should be a parent entity!
                if not same_as.is_sameas_parent_entity():
                    return False
            except:
                return False
        return True

    def validate_sameas_child_entity(self):
        """
        if entity is a child, it cannot have any other entity pointing same_as to
        itself. Possible, it was a parent and now being changed to a child with
        references to itself still existing!
        """
        if self.get_sameas_child_entities() and not self.is_sameas_parent_entity():
            return False
        return True

    def save(self, *args, **kwargs):
        """
        sets the value of active flag based on the status

        does the basic validations and defaults the values for same_as and
        display_name

        # things to check
        scenario:
        ID   Name      Same_as
        1000 'Khaitan' 1000             (parent)
        or 1000 'Khaitan' ''             (parent)
        1001 'Khaitan & Co.' 1000
        1002 'Khaitan & Co' 1000

        1. check if same_as exists and belongs to the same type as self and is active!
        2. same_as should always be a parent entity
        3. display_name can be filled only if enitity is a parent entity
        4. other entities can have same_as point to this entity, only if this
        entity is a same as parent entity.
        eg if self is 1001, you cannot have:
        1002 'Khaitan & Co Ltd' 1001, since 1001 is not a parent entity
        """
        if self.validate_same_as(self.same_as) and \
                self.validate_sameas_child_entity() and \
                self.validate_display_name(self.display_name):

            # all looks good - update the flag and save it!
            # update the active flag based on the status
            if not self.active == self.get_active_status():
                self.active = self.get_active_status()
                import penseive.signals
                # raise the signal to update the corresponding EntityItems
                penseive.signals.updated_entityitem_active_flag.send(
                    sender=self, entity=self, active=self.active)

            super(Entity, self).save()
        else:
            # raise exceptions
            pass


# define the Penseive Item and their relationships here
class PenseiveItem(models.Model):
    """
    Map the "item" to relevant entities, topics, industries etc
    Item in our case will be the Entry
    """
    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField(db_index=True)
    content_object = GenericForeignKey('content_type', 'object_id')

    entities = models.ManyToManyField(Entity, through='EntityItem')
    industry = models.ForeignKey(Industry, null=True, blank=True)

    class Meta:
        unique_together = (('content_type', 'object_id',),)

    def __unicode__(self):
        return u'%s' % (self.content_object.title)

    def display_entities(self, type_name=[], active=False, display=False):
        """
        Display the entities that are associated with this PenseiveItem
        Dictionary of the following format will be returned:
        {
            "Entity Type": [("name1", True), ("name2", False), ("name3", True)]
        }
        if type_name is present only entities that belong to this type will be fetched

        if active is set to True only active entity items will be displayed/indexed
        By default all entity items are displayed/indexed
        """
        # if active flag is set to true get only active entity items
        if active:
            ei = EntityItem.objects.all().filter(penseive_item=self, active=True)
            qs = Entity.objects.filter(id__in=ei.values_list('entity_id', flat=True))

        else:
            ei = EntityItem.objects.all().filter(penseive_item=self)
            qs = Entity.objects.filter(id__in=ei.values_list('entity_id', flat=True))

        # Prepare the result for the View Penseive
        if display:
            r = []
            for i in ei:
                r.append(
                    {'type': i.entity.get_entity_type().name, 'name': i.entity.get_entity_name(), 'active': i.active})

            res = {}
            data = sorted(r, key=itemgetter('type'))
            for k, g in groupby(data, itemgetter('type')):
                res[k] = sorted(g)

            # Prepare the results
            results = {}
            for k in res:
                item = []
                for each in res[k]:
                    item.append((each['name'], each['active']))
                results[k] = item
            return results

        else:

            if type_name:
                qs = qs.filter(type__name__in=type_name)

            # For every entity we will fetch all its parent across all
            # hierarchies
            # eg if we have the following parent - child hierarchy for entity IITD
            # ORGANIZATION
            # |--UNIVERSITY
            # |    |--IITD
            # then we fetch UNIVERISITY and ORGANIZATION and make sure it gets indexed
            # along with IITD

            result = []
            while qs.count() > 0:
                result.extend(qs)
                p = list(qs.exclude(parent__isnull=True).values_list('parent', flat=True))
                if p:
                    qs = Entity.objects.filter(id__in=p)
                else:
                    qs = Entity.objects.none()

            r = []
            for i in list(set(result)):
                r.append({'type': i.get_entity_type().name, 'name': i.get_entity_name(), 'active': i.active})

            res = {}
            data = sorted(r, key=itemgetter('type'))
            for k, g in groupby(data, itemgetter('type')):
                res[k] = sorted(g)

            # Prepare the results
            results = {}
            for k in res:
                item = []
                for each in res[k]:
                    item.append((each['name'], each['active']))
                results[k] = item
            return results


class EntityItem(models.Model):
    penseive_item = models.ForeignKey(PenseiveItem)
    entity = models.ForeignKey(Entity)
    type = models.ForeignKey(EntityType)
    relevance = models.FloatField(default=0)

    # create index on active field
    # CREATE INDEX "penseive_entityitem_active" ON "penseive_entityitem" ("active");
    active = models.BooleanField(db_index=True)

    created_on = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('type', '-relevance')

    def save(self, *args, **kwargs):
        """
        update the type information, this field has been added to
        denormalize this particular table as the type field will be used
        effectively. Make sure this field is only updated from the backend
        """
        self.type = self.entity.type

        # Note: item will always be active unless:
        # relevance threshold is not met
        # or entity type is inactive
        # or entity itself is inactive
        if not self.relevance >= self.type.relevance_threshold \
                or not self.type.active or not self.entity.active:
            self.active = False
        super(EntityItem, self).save()


class QuoteItem(models.Model):
    '''
    class to store the Quote information retrieved from Calais. Every quote is
    stored against the Entity Person i.e. (entity column) who said the quote in
    the story which is being analyzed.

    If Calais doesnt return the Entity Person Name along with the quote, it returns
    the hash of the person who said or has said the quote according to calais,
    then the potenial match i.e. the most likely Entity to have said that quote
    is populated in the potential_match Entity column, which can be set right later
    from the Admin Interface.


    CREATE TABLE "penseive_quoteitem" (
    "id" serial NOT NULL PRIMARY KEY,
    "penseive_item_id" integer NOT NULL REFERENCES "penseive_penseiveitem" ("id") DEFERRABLE INITIALLY DEFERRED,
    "entity_id" integer REFERENCES "penseive_entity" ("id") DEFERRABLE INITIALLY DEFERRED,
    "potential_match_id" integer NOT NULL REFERENCES "penseive_entity" ("id") DEFERRABLE INITIALLY DEFERRED,
    "quote_text" text NOT NULL,
    "active" boolean NOT NULL,
    "created_on" timestamp with time zone NOT NULL,
    "updated_on" timestamp with time zone NOT NULL
    );

    CREATE INDEX "penseive_quoteitem_penseive_item_id" ON "penseive_quoteitem" ("penseive_item_id");
    CREATE INDEX "penseive_quoteitem_entity_id" ON "penseive_quoteitem" ("entity_id");
    CREATE INDEX "penseive_quoteitem_potential_match_id" ON "penseive_quoteitem" ("potential_match_id");
    CREATE INDEX "penseive_quoteitem_active" ON "penseive_quoteitem" ("active");
    CREATE INDEX "penseive_quoteitem_created_on" ON "penseive_quoteitem" ("created_on");

    '''
    penseive_item = models.ForeignKey(PenseiveItem)
    entity = models.ForeignKey(Entity, limit_choices_to={'type__name': 'Person'}, related_name='exact_match',
                               blank=True, null=True)
    potential_match = models.ForeignKey(Entity, limit_choices_to={'type__name': 'Person'},
                                        related_name='potential_match', blank=True, null=True)
    quote_text = models.TextField()
    active = models.BooleanField(db_index=True)

    created_on = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_on = models.DateTimeField(auto_now=True)

    def get_absolute_url(self):
        return reverse('cms.views.detail_by_id',
                       args=[self.penseive_item.object_id])

    def __unicode__(self):
        return u'%s' % (self.quote_text)

