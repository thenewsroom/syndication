from bs4 import BeautifulSoup as bs
import socket, mechanize, re, time, urllib2
from HTMLParser import HTMLParseError
import cookielib
from story.service import _read_url

REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/40.0.2214.45 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'accept-language': 'en-US,en;q=0.8'
}

class Spider(object):
    """
    """

    ERROR_DICT = {"REQUEST DISALLOWED BY ROBOTS.TXT"        : 403,
                  "NOT FOUND"                               : 404,
                  "TIMED OUT"                               : 408,
                  "[ERRNO -2] NAME OR SERVICE NOT KNOWN"    : 500,
                  "INTERNAL SERVER ERROR"                   : 500,
                  "[ERRNO 111] CONNECTION REFUSED"          : 403,
                  "[ERRNO 113] NO ROUTE TO HOST"            : 500,
                  "FORBIDDEN"                               : 403,
                  }

    def fetch_page_data(self, url):
        """
        This is to read url and it returns a tuple, which contains HTML DOM structure data,
        response status code and response message.
        """
        status = None
        rootError = None
        try:
            res = _read_url(url)
            status = res.status_code
            data = res.text
        except (mechanize.HTTPError, mechanize.URLError) as e:
            try:
                br = mechanize.Browser()
                cj = cookielib.LWPCookieJar()
                br.set_cookiejar(cj)
                br.addheaders = [
                        ('User-Agent', 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11'),
                        ('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'),
                        ]
                br.set_handle_equiv(True)
                br.set_handle_redirect(True)
                br.set_handle_referer(True)
                br.set_handle_robots(False)
                # Follows refresh 0 but not hangs on refresh > 0
                br.set_handle_refresh(mechanize._http.HTTPRefreshProcessor(), max_time=1)
                br.open(url, timeout=15.0)
                res = br.response()
                data = res.read()
                status = res.code
            except (mechanize.HTTPError, mechanize.URLError) as e:    
                rootError = str(e.reason).upper()
                if rootError in self.ERROR_DICT.keys():
                    time.sleep(4)
                    headers = { 'User-Agent' : 'Mozilla/5.0' }
                    req = urllib2.Request(url, None, headers)
                    try:
                        res = urllib2.urlopen(req, timeout=30)
                        data = res.read()
                        status = res.code
                    except urllib2.HTTPError, e:
                        data = e.read()
                        if len(data) > 20000:
                            status = 200
                        else:
                            data = "CNFD"
                            status = self.ERROR_DICT[rootError]
                    except (urllib2.URLError, socket.timeout, socket.error), e:
                        data = "CNFD"
                        status = self.ERROR_DICT[rootError]
                    if not data:
                        status = self.ERROR_DICT[rootError]
                else:
                    data = "CNFD"
                    try:
                        status = e.code
                    except AttributeError, e:
                        status = 404
        except (KeyError, IndexError, RuntimeError):
            # For some url mechanize failed to read them.
            # 1. url = u'http://ysa.gov.ae/ar/%D8%A7%D9%84%D8%A3%D8%AE%D8%A8%D8%A7%D8%B1-%D8%A7%D9%84%D8%B5%D9%81%D8%AD%D8%A9-1'
            #    Error: KeyError
            # 2. url = "http://www.mzv.cz/abudhabi"
            #    Error: RuntimeError: maximum recursion depth exceeded while calling a Python object
            # 3. url = "http://www.slu.edu/newsroom"
            #    Error: IndexError
            # TO DO: reason?
            url = str(url)
            res = urllib2.urlopen(url, timeout=10)
            status = res.code
            data = res.read()
        except (socket.timeout, socket.error):
            try:
                res = urllib2.urlopen(url, timeout=20)
                status = res.code
                data = res.read()
            except:
                data = "CNFD"
                status = 408
        if status == 200:
            msg = 'OK'
        else:
            msg = rootError
        return data, status, msg

    def get_content_tag(self, data, tag_name=None, tag_attr=None,
                        tag_attr_value=None, parser="html.parser"):
        """
        Get the required content from area pattern stored in the system
        """
        try:
            soup = bs(data, parser)
        except HTMLParseError:
            data = tidy_data(data)
            try:
                soup = bs(data, parser)
            except HTMLParseError:
                soup = bs(data, "html5lib")

        content_tag = None
        if tag_name:
            if tag_attr == 'href':
                content_tag = soup.find(
                    tag_name, {tag_attr: re.compile(tag_attr_value)}
                )
                if not content_tag:
                    soup = bs(data, "html5lib")
                    content_tag = soup.find(
                        tag_name, {tag_attr: re.compile(tag_attr_value)}
                    )
            elif tag_name in ['item', 'entry']:
                content_tag = soup.find(tag_name).find(
                    'title') if soup.find(tag_name) else None
            elif tag_name in ['pubdate']:
                content_tag = soup.find(tag_name)
            else:
                content_tag = soup.find(tag_name, {tag_attr:tag_attr_value})
                if not content_tag:
                    soup = bs(data, "html5lib")
                    content_tag = soup.find(tag_name, {tag_attr:tag_attr_value})
        return content_tag

    def get_text(self, content_tag):
        """
        Remove html elements and fetch only text
        """
        if content_tag:
            plain_text = content_tag.get_text()
            plain_text = re.sub("\s+", " ", plain_text).strip()
            return plain_text