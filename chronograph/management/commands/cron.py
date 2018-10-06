import logging
import datetime

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Runs all jobs that are due.'
    
    def handle(self, *args, **options):
        from chronograph.models import Job
        start_time = datetime.datetime.now()
        for job in Job.objects.due():
            logger.info(u'Processing JobID: {}'.format(job.id))
            job.run()
            logger.info(
                u'Processed JobID: {}, TimeElapsed: {}'.format(
                    job.id, (datetime.datetime.now() - start_time)
                )
            )