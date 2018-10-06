# import urllib, urllib2
# import simplejson
#
# from cutils.utils import unicode_to_ascii
#
# class PenseiveTaggerAPI(object):
#     """
#     An API to Interact with Rule Engine
#     """
#     def __init__(self):
#         self.headers = {'Content-type': 'application/x-www-form-urlencoded; charset=utf-8'}
#         self.url = "http://sites.contify.com/api/penseive/autotagger/"
#         self.params = {}
#         self.result = {}
#
#     def getTags(self, title=u"None", body=u"None"):
#         self.params["title"] = unicode(unicode_to_ascii(title))
#         self.params["body"] = unicode(unicode_to_ascii(body))
#         self.params["api_key"] = 'akdhid46343hdsjsj1poer'
#         self.params["internalTags"] = True
#         self.params = urllib.urlencode(self.params)
#         try:
#             request = urllib2.Request(self.url, data=self.params, headers=self.headers)
#             response = urllib2.urlopen(request)
#             self.result = simplejson.loads(response.read())
#         except:
#             self.result['Error'] = "Error in fetching tags from AutoTaggerJSON"
#         return self.result
#
#     def getIndustries(self, result):
#         if result:
#             if result.has_key('Industry'):
#                 for d in result['Industry']:
#                     if d.has_key('classifierBased'): del d['classifierBased']
#                     if d.has_key('ruleBased'): del d['ruleBased']
#                 return [dict(t) for t in set([tuple(d.items()) for d in result['Industry']])]
#             else:
#                 return []
#         else:
#             return []