"""
Utils file for Queues - XML generation for each "format"
TODO: Handle exceptions
"""

try:
    from xmlgen import makeXml, xml
except ImportError:
    sys.stderr.write("Error: Unable to import makeXML and xml, please install xmlgen! - http://code.google.com/p/xml4py/wiki/Documentation")
    sys.exit(1)

from cms.models import Entry
    
def utext(data):
    try:
        val = str(data)
    except UnicodeEncodeError:
        # obj is unicode
        val = unicode(data).encode('unicode_escape') 
    return val

def default(e, u_id = None, contact = None):
    """
    Returns the Entry e in XML format, uses u_id as the uniqid
    If no u_id is passed - foll will be used: <acc>_<pub>_00000<pk>
    """
    if not u_id:
        uniqid = "%s_%s_%010d" %(e.publication.account.slug, e.publication.slug, e.pk)
    else:
        uniqid = u_id
    
    # let's get the contact info
    if not contact:
        from django.conf import settings
        contact = settings.CONTIFY_CONTACT

    #try:
    #    body = str(e.body_html)
    #except UnicodeEncodeError:
    #    # obj is unicode
    #    body = unicode(e.body_html).encode('unicode_escape') 

    x = makeXml(
        xml.Document(
            xml.Headline(xml.PrimaryHeadline(utext(e.title)), xml.SecondaryHeadline()),
            xml.Body(xml.Dateline(xml.ContentDate(e.pub_date), xml.Location(),
                xml.Attribution(e.publication)), utext(e.body_html) + "<p>" + self.publication.get_copyright() + "</p>"),
            xml.UniqID(uniqid), xml.Contact(contact), xml.Copyright(e.publication.get_copyright()),
            ReleaseTime=e.created_on, TransmissionID=e.pk),
        encoding = "utf-8"
    )
    
    return u_id, x