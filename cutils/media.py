"""
define modules to handle media related activities
"""
import urlparse, os
import logging
import logging.config
from urllib import urlretrieve

from BeautifulSoup import BeautifulSoup as bsoup

from django.utils.encoding import smart_unicode

from cutils.utils import ContifyValidationError


logger = logging.getLogger(__name__)


MEDIA_MIME_TYPE = {
    ".bm" :	"image/bmp",
    ".bmp":     "image/bmp",
    ".gif": 	"image/gif",
    ".jpe": 	"image/jpeg",
    ".jpeg": 	"image/jpeg",
    ".jpg": 	"image/jpeg",
    ".jpg": 	"image/pjpeg",
    ".pct": 	"image/x-pict",
    ".pcx": 	"image/x-pcx",
    ".pgm": 	"image/x-portable-graymap",
    ".pic": 	"image/pict",
    ".pict": 	"image/pict",
    ".png":	    "image/png",
    ".qif": 	"image/x-quicktime",
    ".qti": 	"image/x-quicktime",
    ".qtif": 	"image/x-quicktime",
    ".tif": 	"image/tiff",
    ".tiff": 	"image/tiff",
    ".x-png": 	"image/png",
}


def img_to_media(data_html, producer, prefix=None, download_to=None):
    """
    TODO:
    * Height and width being ignored
    * All a href to images being ignored
    * Image Caption - if image within divs is not being considered
    
    scans the data for img tags and replaces them with nsml standard media tags
    if the img does not exist at the src, it will be removed
    files will be downloaded if the location is specified
    <img src="filename.jpg" alt="#alt_text#" align="#alignment#" width="#w#" height="#h#"/>
    <media media-type="image" style="align:#alignment#">
        <media-reference mime-type="image/jpeg" source="filename.jpg" alternate-text="#alt-text#" height="#h#" width="#w#"></media-reference>
        <media-caption>
            #caption#
        </media-caption>
        <media-producer>
            source
        </media-producer>
    </media>    
    @param data_html data in html format
    @param source source of the image, should be the publication or the account
    @param check_exists if True, will check if file exists and update the tags, else remove the instance
    @param download_to location where the files needs to be downloaded, optional
    @return data with img tags replace by media tags
    """
    soup = bsoup(data_html)
    src_list = []
    # remove a href to images!!
    for image in soup.findAll("img"):
        new_img_tag = ''
        src = ''
        try:
            # extract the elements from img tag
            if image.has_key("src"):
                src = image["src"]
                
                filename = src.split("/")[-1]
                if prefix:
                    filename = prefix + "_" + filename
                
                alt = "" # default to blank
                if image.has_key("alt"):
                    alt = image["alt"]
        
                align='align:right' # default to right
                if image.has_key("align"):
                    align = image["align"]
                
                if image.has_key("width") and image.has_key("height"):
                    width = image["width"]
                    height = image["height"]
                    
                    new_img_tag = get_media_tags(filename, producer, alt, height=height, width=width, align=align)
                else:
                    new_img_tag = get_media_tags(filename, producer, alt, align)
            
                # ignore height and width for now
                new_img_tag = get_media_tags(filename, producer, alt, align)
            else:
                # error - src has to be there!!
                raise ContifyValidationError("Image src missing, img tag: %s" %(image))
        except ContifyValidationError, e:
            # move on to the next image, catch the exception - log it and move on
            logger.error(e)
        finally:
            # download the image to a local location
            # replace the current img tag with the new_img_tag
            if download_to:
                if not os.path.isdir(download_to):
                    os.makedirs(download_to, mode=0755)
                
                if new_img_tag and not os.path.isfile(os.path.join(download_to, filename)):
                    try:
                        urlretrieve(src, os.path.join(download_to, filename))
                        logger.debug("downloaded %s" %(src))
                    except IOError, e:
                        logger.error("Unable to download file from url: %s. Error %s" %(src, e))
            
            image.replaceWith(new_img_tag)

    # remove all unwanted href pointing to images in the body
    return smart_unicode(remove_img_href(soup).renderContents())

def get_media_tags(filename, producer, alt="", align="align:right", height=None, width=None, caption=''):
    """
    prepares the media tags
    @param filename name of the file, this will go in the source tag
    @param producer producer of the content
    @param alt alternate text, default is blank
    @param height image height (optional)
    @param width image width (optional)
    @param align image style, alignment, default set to align:right
    @param caption image caption (optional)
    @return the media xml
    """
    from xmlgen import makeXml, xml
    
    # get the media type and mime type
    type, mime = get_media_mime_type(filename)
    
    if height and width:
        reference_x = xml["media-reference"](__={
            'height': height,
            'width': width,
            'alternate-text': alt,
            'source':filename,
            'mime-type':mime,
            }).xml
    else:
        reference_x = xml["media-reference"](__={
            'alternate-text': alt,
            'source':filename,
            'mime-type':mime,
            }).xml
        
    return xml.media(
        __={'style':align, 'media-type':type},
        _=[reference_x,
           xml["media-caption"](caption).xml,
           xml["media-producer"](producer).xml],
        ).xml

def get_media_mime_type(filename):
    """
    returns the image mime type, extracts the extension from the filename
    uses MEDIA_MIME_TYPE to identify ...
    @param filename name of the file whose mime type needs to be identified
    @return type and the mime-type
    """
    ext = "." + (filename.split(".")[-1])
    ext = ext.strip().lower()
    if  MEDIA_MIME_TYPE.has_key(ext):
        mime = MEDIA_MIME_TYPE[ext]
        type = mime.split("/")[0]
        return type, mime
    
    raise ContifyValidationError("Unknown mime type for file: %s" %(filename))

def remove_img_href(data_soup):
    """
    removes <a href> tags that link to images
    @param data_soup expects a soup element
    @return soup element without hrefs pointing to images
    """
    from django.template.defaultfilters import removetags
    for a in data_soup.findAll("a"):
        
        # check the url / href of the a tag
        # get the filename, if the extension is an image, remove it!
        if a.has_key("href"):
            href = a["href"]
            filename = href.split("/")[-1]        
            try:
                type, mime = get_media_mime_type(filename)
                if type == "image":
                    clean_a = removetags(a, "a")
                    a.replaceWith(clean_a)                
            except ContifyValidationError, e:
                logger.warn("non image, ignore. Error %s" %(e))
        else:
            logger.warn("No href in the a tag!! %s" %(smart_unicode(a.renderContents())))
    return data_soup
      
def fix_img_urls(base_url, img_src_url):
    """
    Converts the img_src_url to absolute url and checks if the url is actually valid
    @param base_url this is the url of the actual story page or site hosting the story
    @param img_src_url this is the relative or absolute url of the image that needs to be checked
    @return the absolute url for the image
    """
    return urlparse.urljoin(base_url, url)

def remove_images(data_html):
    """
    remove occurences of images from data_html
    if there are any links that do not have any text, will also be removed
    """
    soup = bsoup(data_html)
    
    # remove all images
    for image in soup.findAll("img"):
        image.replaceWith('')
        try:
            logger.debug('removed img: %s' %(image["src"]))
        except KeyError:
            logger.debug('removed img: %s' %("image link was not available"))
    
    # remove links to images or to anything, without any text
    # eg: <a href='http://link/to/some-page'></a>
    # following will be left as it is:
    # <a href='http://link/to/some-page'>some text</a>
    for a in soup.findAll('a'):
        if not a.renderContents().strip():
            a.replaceWith('')
            logger.debug('removed a tag containing: %s' %(a))
    
    return smart_unicode(soup.renderContents())

def img_to_yahoo_media(data_html, producer, prefix=None,):
    """
    TODO:
    * Height and width being ignored
    * All a href to images being ignored
    * Image Caption - if image within divs is not being considered
    
    scans the data for img tags and replaces them with  yahoo nsml standard media tags
    if the img does not exist at the src, it will be removed
    <img src="filename.jpg" alt="#alt_text#" align="#alignment#" width="#w#" height="#h#"/>
    <media media-type="image" style="align:#alignment#">
        <media-reference mime-type="" source="#photo_number"/>
    </media>    
    @param data_html data in html format
    @param source source of the image, should be the publication or the account
    @param check_exists if True, will check if file exists and update the tags, else remove the instance
    @return data with img tags replace by media tags
    """
    # use this with the following template tag if required
    # {{ entry.get_body_with_yahoo_media_tags|xmlsafe|hreftext|safe }}
    # remember TODO, remove nesting of  img tags inside para tags 
    soup = bsoup(data_html)
    # remove a href to images!!
    image_count = 0
    for image in soup.findAll("img"):
        new_img_tag = ''
        src = ''
        try:
            # extract the elements from img tag
            if image.has_key("src"):
                src = image["src"]
                filename = src.split("/")[-1]
                type, mime = get_media_mime_type(filename)
                new_img_tag = """<media style="rightSide" media-type="image">""" + \
                            """<media-reference source="#photo%s" mime-type=""/></media>""" % \
                            image_count  
                image_count += 1
        except ContifyValidationError, e:
            # move on to the next image, catch the exception - log it and move on
            logger.error(e)
        finally:
            image.replaceWith(new_img_tag)

    # remove all unwanted href pointing to images in the body
    return smart_unicode(remove_img_href(soup).renderContents())
    
def get_yahoo_xml_photo_news(data_html, headline):
    """scans the data for img tags and replaces them with  yahoo nsml standard
    newsitem photo tags 
    if the img does not exist at the src, it will be removed"""
    soup = bsoup(data_html)
    image_count = 0
    return_tag_string = ""
    for image in soup.findAll("img"):
        new_img_tag = ''
        src = ''
        try:
            # extract the elements from img tag
            if image.has_key("src"):
                src = image["src"]
                filename = src.split("/")[-1]
                
                alt = "" # default to blank
                if image.has_key("alt"):
                    alt = image["alt"]
                elif image.has_key("title"):
                    alt = image["title"]
              
                if image.has_key("width") and image.has_key("height"):
                    width = image["width"]
                    height = image["height"]
                    
                type, mime = get_media_mime_type(filename)
                
                new_img_tag = """<NewsComponent Duid="photo%s">""" % image_count + \
                """<Role FormalName="Photo"/>""" + \
                """<NewsLines><HeadLine>%s</HeadLine></NewsLines>""" % headline + \
                """<DescriptiveMetadata><Language FormalName="en"/>""" + \
                """</DescriptiveMetadata><NewsComponent>""" + \
                """<Role FormalName="Caption"/><ContentItem>""" + \
                """<MediaType FormalName="Text"/>""" + \
                """<Format FormalName="NITF"/><DataContent><nitf><body>""" + \
                """<body.content><p>%s</p></body.content>""" % alt + \
                """</body></nitf></DataContent></ContentItem></NewsComponent>""" + \
                """<NewsComponent Duid="base%s">""" %image_count + \
                """<Role FormalName="BaseImage"/>""" + \
                """<ContentItem Href="%s">""" % src + \
                """<MediaType FormalName="Photo"/>""" + \
                """<Format FormalName="JPEG Baseline"/>""" + \
                """<MimeType FormalName="%s"/>""" % mime + \
                """</ContentItem></NewsComponent></NewsComponent>"""                      
                image_count += 1
        except ContifyValidationError, e:
            # move on to the next image, catch the exception - log it and move on
            logger.error(e)
        finally:
            return_tag_string += new_img_tag
    return return_tag_string
        