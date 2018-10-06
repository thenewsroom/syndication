#
import sys
import re
import htmlentitydefs
import unicodedata
from BeautifulSoup import BeautifulSoup, Tag, Comment
# from django.utils.html import remove_tags

from django.utils.encoding import smart_unicode, DjangoUnicodeDecodeError

from django.conf import settings

# Month Dict Mapping as per given list of months in guide lines
# Jan. Feb. March April May June July Aug. Sept. Oct. Nov. Dec.

MONTH_MAP = {
    1: "Jan.",
    2: "Feb.",
    3: "March",
    4: "April",
    5: "May",
    6: "June",
    7: "July",
    8: "Aug.",
    9: "Sept.",
    10: "Oct.",
    11: "Nov.",
    12: "Dec.",
}

TAG_LIST = ["a", "abbr", "acronym", "address", "area", "article", "b", "base", "bdo", "big", "blockquote", "body", "br", "button",
            "caption", "cite", "code", "col", "colgroup", "dd", "del", "dfn", "div", "dl", "DOCTYPE", "dsfcontenttitle",
            "dt", "em", "entry", "fieldset", "font", "form", "h1", "h2", "h3", "h4", "h5", "h6", "head", "html", "hr",
            "i", "img", "input", "ins", "item", "kbd", "label", "legend", "li", "link", "map", "meta", "nobr", "noscript",
            "object", "ol", "optgroup", "option", "p", "page", "param", "pre", "pubdate", "q", "samp", "script", "section",
            "select", "small", "span", "strong", "style", "sub", "summary", "sup", "table", "tbody", "td", "textarea", "tfoot",
            "th", "thead", "time", "title", "tr", "tt", "u", "ul", "var"]

TAG_ATTRS = ['abbr', 'accept', 'accept-charset', 'accesskey', 'action', 'align', 'alink', 'alt', 'archive', 'axis',
             'background', 'bgcolor', 'border', 'cellpadding', 'cellspacing', 'char', 'charoff', 'charset', 'checked',
             'cite', 'class', 'classid', 'clear', 'code', 'codebase', 'codetype', 'color', 'cols', 'colspan', 'compact',
             'content', 'coords', 'data', 'data-bind', 'datetime', 'declare', 'defer', 'dir', 'disabled', 'enctype', 'face', 'for',
             'frame', 'frameborder', 'headers', 'height', 'href', 'hreflang', 'hspace', 'http-equiv', 'id', 'ismap',
             'label', 'lang', 'language', 'link', 'linktype', 'longdesc', 'marginheight', 'marginwidth', 'maxlength', 'media',
             'method', 'multiple', 'name', 'nohref', 'noresize', 'noshade', 'nowrap', 'object', 'onblur', 'onchange',
             'onclick', 'ondblclick', 'onfocus', 'onkeydown', 'onkeypress', 'onkeyup', 'onload', 'onmousedown',
             'onmousemove', 'onmouseout', 'onmouseover', 'onmouseup', 'onreset', 'onselect', 'onsubmit', 'onunload',
             'profile', 'prompt', 'property', 'pubdate', 'readonly', 'rel', 'rev', 'rows', 'rowspan', 'rules', 'scheme', 'scope', 'scrolling',
             'selected', 'shape', 'size', 'span', 'src', 'standby', 'start', 'style', 'summary', 'tabindex', 'target',
             'text', 'title', 'type', 'usemap', 'valign', 'value', 'valuetype', 'version', 'vlink', 'vspace', 'width']


PUB_ID_DICT = {
    "China Business News": "252",
    "India Automobile News": "253",
    "India Energy News": "207",
    "India Insurance News": "243",
    "India Investment News": "209",
    "Indian Banking News": "210",
    "Indian Patents News": "20",
    "Indian Trademark News": "208",
    "India Pharma News": "206",
    "India Public Sector News": "25",
    "India Retail News": "188",
    "India Telecom News": "431",
    "Indonesia Government News": "110",
    "Islamic Finance News": "21",
    "Russia Business News": "429",
    "Singapore Government News": "108",
    "UAE Government News": "189",
    "Hong Kong Government News": "109",
    "Industry Reports": "414",
}


def is_valid_html_tag(tag_name):
    """ returns true for a valid HTML tag
    """
    return tag_name in TAG_LIST


##########################################################################
# HTML Cleaning
##########################################################################

def clean_html(html):
    """
    Remove HTML tags from the given string.
    """

    # First we remove inline JavaScript/CSS:
    cleaned = re.sub(r"(?is)<(script|style).*?>.*?(</\1>)", "", html.strip())
    # Then we remove html comments. This has to be done before removing regular
    # tags since comments can contain '>' characters.
    cleaned = re.sub(r"(?s)<!--(.*?)-->[\n]?", "", cleaned)
    # Next we can remove the remaining tags:
    cleaned = re.sub(r"(?s)<.*?>", " ", cleaned)
    # Finally, we deal with whitespace
    cleaned = re.sub(r"&nbsp;", " ", cleaned)
    cleaned = re.sub(r"  ", " ", cleaned)
    cleaned = re.sub(r"  ", " ", cleaned)
    return cleaned.strip()


def clean_url(url):
    from urllib import urlopen
    html = urlopen(url).read()
    return clean_html(html)


def clean_data(data):
    """
    @param data String to be cleaned
    @return String without ^M, \n, \xc2, \x02, \x1d, {mosimage}
    """
    p = re.compile('\xc2|\x02|\x1d|{mosimage}|')
    data = p.sub('', data)
    m = re.compile('\r+|\n+|\t+')

    return m.sub(' ', data)

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
        if re.sub(r'\s|\&nbsp\;|\\xa0', "", striptags(tmp)) == '':
            d = []
            d = tmp.findAll('img')
            if not d:
                s.extract()
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
        soup = BeautifulSoup(data)
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
    data_html = fix_dirty_ampersands(unescape(data_html))

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

def br_to_p(data):
    """
    given the string in data argument, all linebreaks are replaced
    with paragraph tags and returned back
    """
    result = "<p>%s</p>" %re.sub("\<br[\s]*\/\>", "</p><p>", data)
    return result

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
    if not data_html:
        return ""

    # strip unwanted spaces, comments, clean p tags and
    # convert to unicode - smartly!
    # tidy up the html tags

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
        dataSoup = BeautifulSoup(data_html)
        # data_html = remove_data_images(data_html)
        imgTags = dataSoup.findAll('img')
        [imgTag.extract() for imgTag in imgTags]
        data_html = dataSoup.renderContents()

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
