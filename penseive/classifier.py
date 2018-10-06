"""
Text Classifier - Wrapper around the Custom Classifier app built by Cohan
"""

import urllib
import urllib2
import logging
from operator import itemgetter

from BeautifulSoup import BeautifulStoneSoup

from cutils.utils import unicode_to_ascii

empty_soup = BeautifulStoneSoup("")

CLASSIFIER_URL = "http://classifier.contify.com:8085/contify/cl101"


class Classifier():
    """
    Wrapper around the Custom Classifier app built by Cohan

    >>> text = '<p>CAG: Irregularities in Purchase of Drugs under NRHM</p><p>New Delhi, May 20: The Comptroller and Auditor General of India (CAG)  has thrown light into serious irregularities  in purchase of drugs under NRHM. Such irregularities include, absence of standard tender process, ignoring of lowest rates, and procurement from blacklisted suppliers involving a total of Rs 36.07 crore loss to the exchequer in many states.<br /><br />The performance audit by CAG on the procurement of drugs under the National Rural Health Mission (NRHM) also noted that while the Union Health Ministry had set up an Empowered Procurement Wing (EPW) and developed a comprehensive procurement manual centrally, in 26 States/UTs, no such procurement manual had been prepared.</p>'
    >>> 
    >>> 
    >>> c = Classifier(text)
    >>> c.print_summary()
    Best Result: Healthcare
    Pharma and Biotechnology (0.0222055755)
    Healthcare (0.0007341888)
    Financial Services (0.0007261282)
    Agriculture (0.0006335343)
    Textiles (0.0004914638)
    Professional Services (0.0003849117)
    Transport and Infrastructure (0.0003615114)
    Consumer Goods (0.0002405135)
    Telecom (0.0002167880)
    Chemicals (0.0001362236)
    Retail (0.0001159000)
    Education (0.0001021805)
    Outsourced Services (0.0000750909)
    Media (0.0000541939)
    Food and Beverages (0.0000317641)
    Materials (0.0000223733)
    Energy (0.0000211609)
    Real Estate (0.0000197222)
    Automobiles (0.0000089047)
    Travel and Tourism (0.0000042117)
    Hotels, Restaurants and Leisure (0.0000037151)
    FMCG (0.0000033119)
    Internet (0.0000024324)
    Information Technology (0.0000015466)
    Capital Goods and Construction &amp; Engineering (0.0000000000)
    Health &amp; Fitness (0.0000000000)

    >>> 
    >>> c.best_result
    'Healthcare'
    >>> # top 3 reults
    >>> 
    >>> for i in c.results[:3]: i['category'], i['probability']
    ... 
    ('Pharma and Biotechnology', 0.022205575526088189)
    ('Healthcare', 0.00073418876468636705)
    ('Financial Services', 0.00072612820497715378)
    >>> 

    """
    
    def __init__(self, text):
        
        self.raw_results = ''
        self.xml_soup = self._fetch_classifications(text)
        self.results = self.get_results()
        self.best_result = self.get_best_result()
        self.high_recall_results = self.get_high_recall_results()
        
    def _fetch_classifications(self, text):
        """
        Fetch the results from the Classifier and store it a dictionary obj
        """
        values = {'DATA': unicode_to_ascii(text)}
        data = urllib.urlencode(values)
        try:
            req = urllib2.Request(CLASSIFIER_URL, data)
            response = urllib2.urlopen(req)
            self.raw_results = response.read()
        except urllib2.URLError, e:
            logging.error("classifier app url %s not responding" %CLASSIFIER_URL)
            return BeautifulStoneSoup("")
        # get the data in soup format!
        return BeautifulStoneSoup(self.raw_results)
    
    def get_best_result(self):
        if self.xml_soup != empty_soup:
            return self.xml_soup.bestresult.category.renderContents()
        return ""
    
    def get_results(self):
        results = []
        if self.xml_soup != empty_soup:
            for s in self.xml_soup.findAll('result'):
                c = s.category.renderContents()
                
                # if probability is not available it is set to null
                # ValueError will be thrown during conversion to float
                # set null to 0.0
                try:
                    p = float(s.probability.renderContents())
                except ValueError:
                    p = 0.0
                
                results.append({'category':c, 'probability': p})
                
            return sorted(results, key=itemgetter('probability'), reverse=True)
        return []
            
    def get_high_recall_results(self):
        high_recall_results = []
        if self.xml_soup != empty_soup:
            r = self.xml_soup.high_recall_results
            if r.category is not None:
                for category in r.findAll('category'):
                    high_recall_results.append({'category' : category.renderContents() })
                return high_recall_results
        return []
            
    def print_summary(self):
        print u'Best Result: %s' % self.best_result
        
        for i in self.results:
            print u'%s (%.10f)' % (i['category'], i['probability'])
