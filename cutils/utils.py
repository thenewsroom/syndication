"""
Common Utilities for Contify App

Kapil B    23-10-2009   Remove empty table tags as part of pre_process_data
Kapil B    22-10-2009   Added EN Dash to unescape function
"""
import os
# from tidylib import tidy_document
import datetime
import htmlentitydefs
import re
import sys
import unicodedata
import urlparse
from enum import IntEnum, unique
from selenium import webdriver
import requests
from requests.adapters import HTTPAdapter

from BeautifulSoup import BeautifulSoup, Tag, Comment
from django.conf import settings
from django.utils.html import strip_tags
from django.utils.encoding import smart_unicode, DjangoUnicodeDecodeError
from django import template

register = template.Library()


class ContifyValidationError(Exception):
    """Something bad happened during validation."""
    pass

BUYERS = [31, 51, 60, 62, 63, 199, 211, 221, 231]


@unique
class Buyers(IntEnum):
    FACTIVA = 31
    THOMSON_REUTERS = 51
    GALE_CENGAGE = 60
    LEXISNEXIS = 62
    PROQUEST = 63
    BLOOMBERG = 199
    ACQUIREMEDIA = 211
    NEWSBANK = 221
    SECURITIES = 231


BUYER_SHORT_NAME_MAP = {
    Buyers.FACTIVA: 'F',
    Buyers.THOMSON_REUTERS: 'TR',
    Buyers.GALE_CENGAGE: 'GC',
    Buyers.LEXISNEXIS: 'LN',
    Buyers.PROQUEST: 'PQ',
    Buyers.BLOOMBERG: 'BB',
    Buyers.ACQUIREMEDIA: 'AM',
    Buyers.NEWSBANK: 'NB',
    Buyers.SECURITIES: 'S',
}

class ContifyDateUtil:
    """
    Date utility that fetches the start and end datetime.datetime objects for
    the selected / current day, week, month, and year
    The start date will always have the time set to 0hrs, 0mins, 0seconds and
    the end date will always have the time set to 23hrs, 59mins, 59seconds
    
    now = ContifyDateUtil()
    s,e = now.today() # start of the day and end of the day
    s,e = now.week() # start of the week and end of the week
    and so on
    
    for a specific date
    dt = ContifyDateUtil(datetime.datetime(2009,5,11,15,31,0))
    dt.week() will give you the start and end dates of the week
    """
    def __init__(self, dt=None):
        if not dt:
            self.dt = datetime.datetime.now()
        elif type(dt) == datetime.datetime:
            self.dt = dt
        elif type(dt) == datetime.date:
            self.dt = datetime.datetime.combine(dt, datetime.time.min)
        else:
            raise ValueError(
                    "unknown format, expecting python datetime/date object only"
            )
    
    def prepare_start_date(self, start):
        """
        start of the day, set the time to
        0 hours,0 minutes,0 seconds, 0 microsecond
        """
        return datetime.datetime.combine(start, datetime.time.min)

    def prepare_end_date(self, end):
        """
        end of the day, set the time to
        23 hours, 59 minutes, 59seconds, 999999 microseconds
        """
        return datetime.datetime.combine(end, datetime.time.max)

    def start(self):
        """set to start of day"""
        return self.prepare_start_date(self.dt)

    def end(self):
        """set to end of day"""
        return self.prepare_end_date(self.dt)

    def today(self):
        dt = self.dt
        return self.prepare_start_date(dt), self.prepare_end_date(dt)
    
    def week(self):
        dt = self.dt
        start_week = self.prepare_start_date(
            dt + datetime.timedelta(days=-dt.weekday(), weeks=0)
        )
        
        # weekday starts from 0, subtract from 6 instead of 7
        end_week = self.prepare_end_date(
            dt + datetime.timedelta(days=6-dt.weekday(), weeks=0)
        )
        
        return start_week, end_week
    
    def month(self):
        dt = self.dt
        import calendar
        start_month = self.prepare_start_date(dt.replace(day=1))
        
        # get the last day of the month form calendar
        wd, ld = calendar.monthrange(dt.year, dt.month)
        end_month = self.prepare_end_date(
            dt.replace(day=ld)
        )
        return start_month, end_month
    
    def year(self):
        start_year = self.prepare_start_date(self.dt.replace(day=1, month=1))
        end_year = self.prepare_end_date(self.dt.replace(day=31, month=12))
        
        return start_year, end_year


@register.filter
def truncate(value, arg):
    """
    Truncates a string after a given number of chars  
    Argument: Number of chars to truncate after
    """
    try:
        length = int(arg)
    except ValueError: # invalid literal for int()
        return value # Fail silently.
    if not isinstance(value, basestring):
        value = str(value)
    if len(value) > length:
        return value[:length] + "..."
    else:
        return value


def clean_data(data):
    """
    @param data String to be cleaned
    @return String without ^M, \n, \xc2, \x02, \x1d, {mosimage}
    """
    p = re.compile('\xc2|\x02|\x1d|{mosimage}|')
    data = p.sub('', data)
    m = re.compile('\r+|\n+|\t+')
    
    return m.sub(' ', data)


def clean_all_html(data_html):
    """
    Performs common html clean-up operations
    * removes empty html tags - table and p
    * removes the html comments
    * removes any style information from p and br tags
    * fixes the ampersands
    """
    # clean the p style elements, get rid of html comments
    # if there are empty p tags, get rid of them
    data_html = clean_html_style(data_html, 'p')

    # if there are empty p tags, get rid of them
    data_html = clean_html_style(data_html, 'table')
    
    # remove empty tables, if any
    data_html = remove_empty_html_tag(data_html, 'table|p')

    # fix the ampersands, unescape the data first - this will ensure
    # all &#x2019 is not converted to &amp;#x2019

    return data_html


def fix_dirty_ampersands(text):
    """
    BeautifulSoup converts R&D to R&D; this code is to fix such issues
    This will ignore all &amp; &#\d+;, which are valid
    This will also ignore &\d+;, which is invalid!!
    """
    # bug: how to ignore &apos; and other html entities?
    # restrict to items that have 1 or 2 characters only ...
    return re.sub(r'&(?!(amp|gt|lt|#\d+))([a-z|A-Z]{1,2});', r'&amp;\2', text)


def contains_junk_ampersands(text):
    """ looks for junk ampersands that match &\d+; eg &8032; """
    
    dirty_amp = re.findall(r'&\d+;', text)
    if dirty_amp:
        return dirty_amp
    return ''


def remove_empty_html_tag(text, tag, extract=[]):
    """
    check if the tag is empty, if yes remove it
    spaces, &nbsp; will be treated as empty
    for further extracting elements you can pass them in the extract list
    
    >>> text = "<p> valid p tags</p><p> <br/> <br/> </p><p>&nbsp;    </p>"
    >>> remove_empty_html_tag(text,'p')
    u'<p> valid p tags</p>'
    >>>
    >>> text = "<p> valid p tags</p><p> <em>junk01</em><br/> <em>more junk</em><br/> <strong>%^$#@</strong></p><p>&nbsp;    </p>"
    >>> remove_empty_html_tag(text,'p', ['em'])
    u'<p> valid p tags</p><p> <br /> <br /> <strong>%^$#@</strong></p>'
    >>> remove_empty_html_tag(text,'p', ['strong'])
    u'<p> valid p tags</p><p> <em>junk01</em><br /> <em>more junk</em><br /> </p>'
    >>> remove_empty_html_tag(text,'p', ['strong', 'em'])
    u'<p> valid p tags</p>' 
    >>> text = "<table><tbody><tr><td>&nbsp;</td></tr><tr><td><em>Agni-III</em></td></tr></tbody></table>"
    >>> remove_empty_html_tag(text, 'table', ['em'])
    u''
    >>> text = "<table><tbody><tr><td>&nbsp;</td></tr><tr><td>Some other text<em>Agni-III</em></td></tr></tbody></table>"
    >>> remove_empty_html_tag(text, 'table', ['em'])
    u'<table><tbody><tr><td>&nbsp;</td></tr><tr><td>Some other text</td></tr></tbody></table>'
    >>> 

    """
    soup = BeautifulSoup((text))
    for s in soup.findAll(re.compile(tag)):
        tmp = s
        
        # extract the extra elements before doing a null check
        for i in extract:
            [x.extract() for x in tmp.findAll(i)]
        # if null check is true, extract from the original soup
    return smart_unicode(soup.renderContents())


def clean_html_style(data, element, remove_comments=True, remove_empty=True):
    """removes the style information associated with html element
    
    >>> t = '<!--  /* Style Definitions */ table.MsoNormalTable	{mso-style-name:"Table Normal";	mso-tstyle-rowband-size:0;	mso-tstyle-colband-size:0;	mso-style-noshow:yes;	mso-style-priority:99;	mso-style-qformat:yes;	mso-style-parent:"";	mso-padding-alt:0in 5.4pt 0in 5.4pt;	mso-para-margin-top:0in;	mso-para-margin-right:0in;	mso-para-margin-bottom:10.0pt;	mso-para-margin-left:0in;	line-height:115%;	mso-pagination:widow-orphan;	font-size:11.0pt;	font-family:"Calibri","sans-serif";	mso-ascii-font-family:Calibri;	mso-ascii-theme-font:minor-latin;	mso-hansi-font-family:Calibri;	mso-hansi-theme-font:minor-latin;} --><p>  </p><p class="MsoNormal" style="margin-bottom: 0.0001pt; line-height: normal;">New Delhi, Aug. 21 -- <strong>Jonathan E. Rathbone, Matthew R., J. Jackson, Thomas C. Stoneberg and ujjaini mitra-shah</strong> of <strong>Wm. Wrigley Jr. Company, </strong>Chicago, U.S.A. have developed a food product container.</p><p class="MsoNormal" style="margin-bottom: 0.0001pt; line-height: normal;">?</p><p class="MsoNormal" style="margin-bottom: 0.0001pt; line-height: normal;">According to the Controller General of Patents, Designs & Trade Marks ?A food product container includes a base and a cover?</p>'
    >>> clean_html_style(t, 'p') 
    '<p>New Delhi, Aug. 21 -- <strong>Jonathan E. Rathbone, Matthew R., J. Jackson, Thomas C. Stoneberg and ujjaini mitra-shah</strong> of <strong>Wm. Wrigley Jr. Company, </strong>Chicago, U.S.A. have developed a food product container.</p><p>?</p><p>According to the Controller General of Patents, Designs & Trade Marks ?A food product container includes a base and a cover?</p>'
    >>> clean_html_style(t, 'p', remove_empty=False)
    '<p> </p><p>New Delhi, Aug. 21 -- <strong>Jonathan E. Rathbone, Matthew R., J. Jackson, Thomas C. Stoneberg and ujjaini mitra-shah</strong> of <strong>Wm. Wrigley Jr. Company, </strong>Chicago, U.S.A. have developed a food product container.</p><p>?</p><p>According to the Controller General of Patents, Designs & Trade Marks ?A food product container includes a base and a cover?</p>'
    >>> clean_html_style(t, 'p', remove_comments=False)
    '<!--  /* Style Definitions */ table.MsoNormalTable\t{mso-style-name:"Table Normal";\tmso-tstyle-rowband-size:0;\tmso-tstyle-colband-size:0;\tmso-style-noshow:yes;\tmso-style-priority:99;\tmso-style-qformat:yes;\tmso-style-parent:"";\tmso-padding-alt:0in 5.4pt 0in 5.4pt;\tmso-para-margin-top:0in;\tmso-para-margin-right:0in;\tmso-para-margin-bottom:10.0pt;\tmso-para-margin-left:0in;\tline-height:115%;\tmso-pagination:widow-orphan;\tfont-size:11.0pt;\tfont-family:"Calibri","sans-serif";\tmso-ascii-font-family:Calibri;\tmso-ascii-theme-font:minor-latin;\tmso-hansi-font-family:Calibri;\tmso-hansi-theme-font:minor-latin;} --><p>New Delhi, Aug. 21 -- <strong>Jonathan E. Rathbone, Matthew R., J. Jackson, Thomas C. Stoneberg and ujjaini mitra-shah</strong> of <strong>Wm. Wrigley Jr. Company, </strong>Chicago, U.S.A. have developed a food product container.</p><p>?</p><p>According to the Controller General of Patents, Designs & Trade Marks ?A food product container includes a base and a cover?</p>'
    """
    try:
        soup = BeautifulSoup(data)
    except:
        cleanedData = data
        soup = BeautifulSoup(cleanedData)
    # remove all comments in this html block
    if remove_comments:
        comments = soup.findAll(text=lambda text:isinstance(text, Comment))
        [comment.extract() for comment in comments]
    
    # remove all occurences of tags like sup, script
    [i.extract() for i in soup.findAll(re.compile('sup|script'))]
        
    # find all occurences of the "element" tag
    for i in soup.findAll(element):
        text = i.renderContents().strip()
        if text:
            new_tag = Tag(soup, element)
            new_tag.insert(0, text)
            i.replaceWith(new_tag)
        elif remove_empty:
            i.extract()
    return smart_unicode(soup.renderContents())


def escape_text(data_html):
    """
    Converts > and < in the html to &gt; and &lt; respectively
    It will not try convert the html tags
    """
    soup = BeautifulSoup(data_html)

    for s in soup.findAll(text=re.compile("<|>")):
        s.replaceWith(s.replace('<', '&lt;').replace('>', '&gt;'))
    return smart_unicode(soup.renderContents())


def convert_to_ascii(data, action='ignore'):
    """
    NOTE: use unicode_to_ascii instead of this ...
    @param action: default action is set to 'ignore'
    convert data into ASCII, action to determine what to do with the non-ASCII characters
    other options are - 'replace' and 'xmlcharrefreplace'
    """
    import unicodedata
    
    # convert to unicode!
    data = unicode(data, errors='ignore')
    
    # return ascii
    return unicodedata.normalize('NFKD', data).encode("ASCII", action)


def utext(data):
    """
    NOTE: use django.utils.encoding.smart_unicode instead of this ...
    
    Converts a string to unicode!
    """
    try:
        val = str(data)
    except UnicodeEncodeError:
        # obj is unicode
        val = unicode(data).encode('unicode_escape') 
    return val

# all encoding related modules to go over here!!!!


def unescape(text):
    """
    Removes HTML or XML character references and entities from a text string.
    Refer to: http://effbot.org/zone/re-sub.htm#unescape-html
    
    @param text The HTML (or XML) source text.
    @return The plain text, as a Unicode string, if necessary.
    """
    def fixup(m):
        text = m.group(0)
        if text[:2] == "&#":
            # character reference
            try:
                if text[:3] == "&#x":
                    return unichr(int(text[3:-1], 16))
                else:
                    return unichr(int(text[2:-1]))
            except ValueError:
                pass
        else:
            # named entity
            try:
                text = unichr(htmlentitydefs.name2codepoint[text[1:-1]])
            except KeyError:
                pass
        return text # leave as is
    return re.sub("&#?\w+;", fixup, text)


# Translation dictionary.  Translation entries are added to this
# dictionary as needed.

CHAR_REPLACEMENT = {
    # ansi characterset and equivalent unicode and html characters
    # refer: http://www.alanwood.net/demos/ansi.html
    # to handle conversion of characters into ASCII hex instead of Unicode Hex
    # eg feedparser does this
    0x91: u"'",  # left single quotation mark
    0x92: u"'",  # right single quotation mark    
    0x93: u'"',  # left double quotation mark
    0x94: u'"',  # right double quotation mark
    0x95: u"*",  # bullet
    0x96: u"-",  # en dash
    0x97: u"-",  # em dash
    0xa0: u" ",  # space
    
    # latin-1 characters that don't have a unicode decomposition
    0xc6: u"AE", # LATIN CAPITAL LETTER AE
    0xd0: u"D",  # LATIN CAPITAL LETTER ETH
    0xd8: u"OE", # LATIN CAPITAL LETTER O WITH STROKE
    0xde: u"Th", # LATIN CAPITAL LETTER THORN
    0xdf: u"ss", # LATIN SMALL LETTER SHARP S
    0xe6: u"ae", # LATIN SMALL LETTER AE
    0xf0: u"d",  # LATIN SMALL LETTER ETH
    0xf8: u"oe", # LATIN SMALL LETTER O WITH STROKE
    0xfe: u"th", # LATIN SMALL LETTER THORN
    0x10: u" ",  # DATA LINK ESCAPE
    0x2013: u"-", # EN DASH
    0x2014: u"-", # EM DASH
    0x2018: u"'", # LEFT SINGLE QUOTATION MARK
    0x2019: u"'", # RIGHT SINGLE QUOTATION MARK
    0x201c: u'"', # LEFT DOUBLE QUOTATION MARK
    0x201d: u'"', # RIGHT DOUBLE QUOTATION MARK
    0x215D: u"5/8", # VULGAR FRACTION FIVE EIGHTHS
    0x215A: u"5/6", # VULGAR FRACTION FIVE SIXTHS
    0x2158: u"4/5", # VULGAR FRACTION FOUR FIFTHS
    0x215B: u"1/8", # VULGAR FRACTION ONE EIGHTH
    0x2155: u"1/5", # VULGAR FRACTION ONE FIFTH
    0x00BD: u"1/2", # VULGAR FRACTION ONE HALF
    0x00BC: u"1/4", # VULGAR FRACTION ONE QUARTER
    0x2159: u"1/6", # VULGAR FRACTION ONE SIXTH
    0x2153: u"1/3", # VULGAR FRACTION ONE THIRD
    0x215E: u"7/8", # VULGAR FRACTION SEVEN EIGHTHS
    0x215C: u"3/8", # VULGAR FRACTION THREE EIGHTHS
    0x2157: u"3/5", # VULGAR FRACTION THREE FIFTHS
    0x00BE: u"3/4", # VULGAR FRACTION THREE QUARTERS
    0x2156: u"2/5", # VULGAR FRACTION TWO FIFTHS
    0x2154: u"2/3", # VULGAR FRACTION TWO THIRDS
}


class unaccented_map(dict):
    """
    Maps a unicode character code (the key) to a replacement code
    (either a character code or a unicode string).
    """

    def mapchar(self, key):
        ch = self.get(key)
        if ch is not None:
            return ch
        
        de = unicodedata.decomposition(unichr(key))
        if key not in CHAR_REPLACEMENT and de:
            try:
                ch = int(de.split(None, 1)[0], 16)
            except (IndexError, ValueError):
                ch = key
        else:
            ch = CHAR_REPLACEMENT.get(key, key)
        self[key] = ch
        return ch

    if sys.version >= "2.5":
        # use __missing__ where available
        __missing__ = mapchar
    else:
        # otherwise, use standard __getitem__ hook (this is slower,
        # since it's called for each character)
        __getitem__ = mapchar


def unicode_to_ascii(unicodestring):
    """
    Convert a unicode string into an ASCII representation, converting non-ascii
    characters into close approximations where possible.
    
    Special thanks to http://effbot.org/zone/unicode-convert.htm
    
    @param Unicode String unicodestring  The string to translate
    @result String
    """
    charmap = unaccented_map()
    return unicodestring.translate(charmap).encode("ascii", "ignore")


def href_to_text(string_data):
    """ converts <a href="www.mysite.com">My Site</a> to
    My Site [www.mysite.com]
    """
    try:
        soup = BeautifulSoup(string_data)
        for i in soup.findAll("a"):
            # if the anchor tag is same as the href link, just strip the anchor tags
            # eg <a href="www.mysite.com">www.mysite.com</a> will be converted to
            # www.mysite.com
            if i.has_key('href'):
                if i.renderContents().strip() == i["href"].strip():
                    i.replaceWith('%s' %(i.renderContents().strip()))            
                else:
                    i.replaceWith('%s (%s)' %(i.renderContents().strip(), i["href"].strip()))
        return soup.renderContents()
    except:
        # eat away the exception, need add it to the logs
        pass
    return string_data


def pre_process_data(
    data_html, remove_cntrlM=True, remove_tags=settings.STRIP_TAGS,
    remove_images=False, insert_linebreaks=False, clean_html=True,
    ascii_friendly=False, tidy=False):
    """
    basic processing to be done on the data before it is saved to the database
    this will be primarily used by aggregators and save method in Entry
    to ensure data consistency
    @param data_html data to be cleaned
    @param tidy if True, will re-order and correct the html tag ordering as per DOM 
    @param remove_cntrlM if True, will remove ^M, \n, {mosimage} etc from the data
    @param remove_tags list of html tags to be stripped, default picked up from settings
    @param remove_images if True, will remove all occurences of img from the source
    @param insert_linebreaks if True, converts linebreaks to <p> tags
    @param clean_html if True, does basic html cleanup
    @param ascii_friendly if True, replaces non-ascii unciode characters with ascii
    @return clean unescaped data, ready to be saved to the database
    """
    # import inside to avoid circular import error
    from cutils.media import remove_images as remove_data_images

    if not data_html:
        return ""
    
    # strip unwanted spaces, comments, clean p tags and
    # convert to unicode - smartly!
    # tidy up the html tags
    if tidy:
        data_html = tidy_data(data_html, option_flags={
            'clean':1,
            'show-body-only':1,
            'indent':0,
            'hide-comments':1})
    
    try:
        data_html = smart_unicode(data_html)
    except DjangoUnicodeDecodeError:
        data_html = smart_unicode(data_html, errors='replace')

    # convert the \n 's to <p> and <br>
    if insert_linebreaks:
        # There are instances when newlines are in between sentences
        # fix the paras first, and then apply the changes to line breaks,
        html_cleaned = "<p>%s</p>" %re.sub(
            r"\.\s*\n",".<br/>" , re.sub(
                r"\.\s*[\n]{2,}", ".</p><p>", data_html))
        # clean all other stray newlines
        html_cleaned = re.sub("\n"," ", html_cleaned)
        # cleanup extra spaces as may be introduced from above(overkill)
        data_html = re.sub("\s{2,}"," ",html_cleaned)
        
    # clean the data
    if remove_cntrlM:
        data_html = clean_data(data_html)
        
    # get rid of the images and links without a text
    if remove_images:
        data_html = remove_data_images(data_html)
        
    # strip the tags
    if not remove_tags:
        pass
    elif remove_tags == "all":
        data_html = strip_tags(data_html)
    else:
        data_html = data_html
    
    # clean the html
    if clean_html:
        data_html = clean_all_html(data_html)
    
    # we want everything in unicode, unescape HTML
    data_html = unescape(data_html)

    if ascii_friendly:
        data_html = smart_unicode(unicode_to_ascii(data_html))

    # remove all unwanted spaces, if something is left of data_html
    if data_html:
        return data_html.strip()
    else:
        return ''


def rel_to_abs_uri(bodytext, baselink):
    """
    converts all links present in bodytext to absolute
    uses baselink to create the absolute uri
    """
    if bodytext is None:
        return ""
    
    if baselink is None:
        return bodytext
    
    soup = BeautifulSoup(bodytext)
    try:
        for reluri in soup.findAll("a"):
            reluri["href"] = urlparse.urljoin(baselink, reluri["href"])
    except KeyError:
        pass
    return soup.renderContents()


def fetch_querystring_value(field, url):
    """
    given the 'field' and 'url', value of the field is returned
    null string is returned if nothing found
    """
    # 1. fetch the query parameters
    query_params = urlparse.urlparse(url).query.replace("&amp;", "&")

    # 2. fetch the list of query fields
    list_of_fields = re.split("&", query_params)
    
    # 3. iterate over the list until a match for the given field is found
    for each in list_of_fields:
        if re.match(field, each):
            # do the needful and exit the loop
            return re.split(field+'=', each)[1]
    return ""


def br_to_p(data):
    """
    given the string in data argument, all linebreaks are replaced
    with paragraph tags and returned back
    """
    result = "<p>%s</p>" %re.sub("\<br[\s]*\/\>", "</p><p>", data)
    return result


# def tidy_data(html_data, option_flags):
#     """
#     given the html chunk, clean it up and return back the data
#     """
#     from tidylib import tidy_document
#     cleaned_data, errors = tidy_document(html_data, options=option_flags)
#     return cleaned_data


def flatten(lst):
    """
    flatten nested lists, taken from:
    http://www.daniweb.com/code/snippet216879.html

    # example usage
    >>> nested = [('a', 'b', ['c', 'd'], ['a', 'b']), ['e', 'f']]
    >>> nested.count("a")
     0   # woops!
    >>> flattened = list( flatten(nested) )
    >>> flattened
     ['a', 'b', 'c', 'd', 'a', 'b', 'e', 'f']
     
    >>> flattened.count("a")
     2   # that's better    
    """
    for elem in lst:
        if type(elem) in (tuple, list):
            for i in flatten(elem):
                yield i
        else:
            yield elem


# def purify_html(data_html, allowed_tags=[]):
#     """
#     cleanup a html chunk and return it with only allowed tags.
#     """
#     if allowed_tags:
#         m = re.findall("<(?P<tag>[^>,/]*)[/]?>", data_html)
#         tag_list =[str(each.strip().lower()) for each in list(set(m))]
#         restricted_tags = [i for i in tag_list if i not in allowed_tags]
#         removeable_tagstring = " ".join(restricted_tags)
#         return removetags(data_html, removeable_tagstring)
#     else:
#         return data_html


def special_char_converter(text):
    text = text.replace(u"\xe2\u20ac\u2122","'").replace(
        u"\xe2\u20ac?",'"').replace(u"\xe2\u20ac\u201d","-").replace(
        u"\xe2\u20ac\u201c","-").replace(u"\xe2\u20ac\u0153",'"').replace(
        u"\xe2\u20ac\u02dc","'").replace(u"\xe2\u20ac\xa6","...").replace(
        u"\xe2\u20ac\u0161",",").replace(u"\xe2\u20ac", '"').replace(
        u"\u2013", '-').replace(u"\xc2\xa0"," ").replace(
        u"\xc2\xad"," ").replace(u"\xc2\xb7"," ").replace(
        u"\u2019","'").replace(u"\u2018","'").replace(u"\xa0"," ")
    return text


def get_html_response_from_browser(url, username=None, password=None):
    if username and password:
        parsed_url = urlparse.urlparse(url)
        url = u'{}{}'.format(parsed_url.netloc, parsed_url.path)
        url = u'http://{}:{}@{}'.format(username, password, url)
        html = requests.get(url).text
        # browser = webdriver.PhantomJS('/usr/lib/node_modules/phantomjs/bin/phantomjs')
        # browser.get(url)
        # html = browser.page_source
        # os.system('killall -9 phantomjs')
    else:
        html = requests.get(url).text
    return html


def queryset_iterator(qs, batchSize=1000):
    """Memory efficient iterator for a queryset-like set of objects.
    """
    qs = qs.order_by('-id')
    total = qs.count()
    for start in range(0, total, batchSize):
        end = min(start + batchSize, total)
        yield (start, end, total, qs[start:end])


def lazy_cached(func):
    def inner(*args, **kwargs):
        if not hasattr(func, 'cached_result'):
            func.cached_result = func(*args, **kwargs)
        return func.cached_result
    return inner


REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/40.0.2214.45 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'accept-language': 'en-US,en;q=0.8'
}


OVERRIDABLE_FUNCTIONS = 'url_get'


class URLGetException(Exception):
    pass


@lazy_cached
def get_global_session():
    session = requests.session()
    session.mount('https://', HTTPAdapter(pool_connections=100, pool_maxsize=100, max_retries=3))
    session.mount('http://', HTTPAdapter(pool_connections=100, pool_maxsize=100, max_retries=3))
    return session


def url_get(state):
    url = state['url']
    timeout = state.get('timeout', 10)
    use_crawlera = state.get('use_crawlera')
    req_headers = state.get('req_headers', REQUEST_HEADERS)
    dont_reuse_session = state.get('dont_reuse_session', False)

    session = get_global_session()

    options = {'url': url,
               'headers': req_headers,
               'timeout': timeout,
               'verify': False}

    if 'cookies' in state and state['cookies']:
        options['cookies'] = state['cookies']

    if use_crawlera:
        response = requests.get('http://proxy.crawlera.com/fetch',
                                headers=req_headers,
                                timeout=timeout,
                                verify=False,
                                params={'url': url},
                                auth=('adb5925b628547c6b17135ff6237f87f', ''))
    elif dont_reuse_session:
        response = requests.get(**options)
    else:
        response = session.get(**options)

    if not response.ok:
        raise URLGetException(u"Failed getting url: {} with return status: '{}' and reason: '{}'".format(
            url,
            getattr(response, 'status_code', 'Unknown'),
            getattr(response, 'reason', 'Unknown')))

    state['response'] = response
    state['url'] = response.url

    parsed_url = urlparse(state['url'])
    state.update({'domain': parsed_url.netloc,
                  'scheme': parsed_url.scheme,
                  'path': parsed_url.path,
                  'params': parsed_url.params,
                  'query': parsed_url.query,
                  'fragment': parsed_url.fragment})