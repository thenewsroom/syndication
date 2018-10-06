import datetime
import django.dispatch

# define signals
refresh_entry_qs = django.dispatch.Signal(providing_args = ["entry"])
refresh_entry_txqs = django.dispatch.Signal(providing_args = ["entry"])

# these signals contain the user information "publishing" the Entry
# it was created to pass the "user" information in the signal
# primarily used when a ManualEntry item is updated from Entry admin screen
# in most of the scenarios you should use the post_save signal,
# only if you need user, use the following
post_publish_entry_with_user = django.dispatch.Signal(
    providing_args = ["entry", "user"])
post_reject_entry_with_user = django.dispatch.Signal(
    providing_args = ["entry", "user"])


def approval_handler(sender, **kwargs):
    """
    handles the reject and publish signals for all updates via the Entry admin
    screen.
    Checks if the instance belongs to ManualEntry and updates the approval fields
    """
    
    entry = kwargs['entry']
    user = kwargs['user']

    try:
        from content_management.models import ManualEntry
        if entry.status in [-1, 2] and not (entry.send_to_industryfeed_buyers.exists() or entry.industry_rejected_news):
            mentry = ManualEntry.objects.get(id = entry.id)
            mentry.appproved_on = datetime.datetime.today()
            mentry.approved_by = user
            mentry.save()

    except ManualEntry.DoesNotExist:
        # not an instance of ManualEntry, ignore and move on
        pass

# listen for signals    
post_publish_entry_with_user.connect(approval_handler)
post_reject_entry_with_user.connect(approval_handler)
    
