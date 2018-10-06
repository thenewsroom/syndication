import datetime
import django.dispatch

from content_management.models import Entry
from content_management.signals import refresh_entry_qs, refresh_entry_txqs
from cutils.utils import unicode_to_ascii


def is_duplicate_title(new_title, stored_titles):
    stored_titles = [unicode(unicode_to_ascii(t)) for t in stored_titles]
    new_title = unicode(unicode_to_ascii(new_title))
    if new_title in stored_titles:
        return True
    return False


def _is_a_valid_entry_to_add_in_transmission_queue(entry, txq):
    """
    This validation is basically for ie online and fe online
    content transmission.
    For Bloomberg Queue:
       It checks duplicate ie online title or fe online title in ie regular
       or fe regular entry titles created on last 2 days

    For Other Queues it doesn't check cross ie publication's duplicate entries
    """
    # lets set Bloomberg's queue id as default txq_id, which is 30
    _bloomberg_q_buyer_id = 199
    _fe_regular_pub_id = 2
    _ie_regular_pub_id = 3
    _fe_online_pub_id = 315
    _ie_online_pub_id = 314
    _regular_pub_ids = [_fe_regular_pub_id, _ie_regular_pub_id]
    _online_pub_ids = [_ie_online_pub_id, _fe_online_pub_id]

    current_buyer_id = txq.buyer.id
    if current_buyer_id == _bloomberg_q_buyer_id and (
                entry.publication.id in _online_pub_ids):
        today = datetime.datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        date_range = today - datetime.timedelta(days=2)
        entry_qs = Entry.objects.filter(
            publication__id__in=_regular_pub_ids, created_on__gte=date_range
        )
        title_list = entry_qs.values_list('title', flat=True)
        if is_duplicate_title(entry.title, title_list):
            return False
    # lets check if exclude_to_buyer is populated and
    # current_buyer_id is available in exclude_to_buyers field
    if (entry.exclude_to_buyers and exclude_to_buyer_map.get(
            current_buyer_id)) and (
                exclude_to_buyer_map.get(
                    current_buyer_id) in entry.exclude_to_buyers):
        return False
    return True


# define the Signal listeners and handlers here
def update_qs(entry):
    from queues.models import QItem

    qi, created = QItem.objects.get_or_create(entry = entry)
    qi.update_qs()


def update_entry_qs_handler(sender, **kwargs):
    """
    on every save of an entry update the QItem table
    """
    # check if 'entry' is present in the kwargs
    update_qs(kwargs['entry'])


def update_entry_txq_handler(sender, **kwargs):
    """
    add entry to TransmissionQItem
    """
    # fetch parameters
    entry = kwargs['entry']
    action = kwargs['action']
    
    # make sure a valid 'entry' exists
    from queues.models import TransmissionQ, KeywordTransmissionQ
    
    # only add items that belong to TransmissionQ,
    # but not to KeywordTransmissionQ
    tq = TransmissionQ.objects.all().values_list('id', flat=True)
    ktq = KeywordTransmissionQ.objects.all().values_list('id', flat=True)
    valid_q = [a for a in tq if a not in ktq]
    for txq in TransmissionQ.objects.filter(id__in=valid_q):
        if _is_a_valid_entry_to_add_in_transmission_queue(entry, txq):
            eqs = Entry.objects.filter(id=entry.id)
            txq.add_items(eqs, action=action)
    
# listen to the refresh entry qs signal!!
refresh_entry_qs.connect(update_entry_qs_handler) #, sender=Entry, weak=True, dispatch_uid=None)
refresh_entry_txqs.connect(update_entry_txq_handler)
