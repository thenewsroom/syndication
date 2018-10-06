"""
define all Penseive related exceptions here
"""

class PenseiveError(Exception):
    """A generic exception for all others to extend."""
    pass

class NotImplementedError(PenseiveError):
    """Missing required module definition"""
    pass

class TagFetchError(PenseiveError):
    """Error fetching the tags."""
    pass

class OpenCalaisTagFetchError(TagFetchError):
    """Error fetching the tags from Calais."""
    pass

class AlreadyRegistered(PenseiveError):
    """Raised when a model is already registered with a site."""
    pass

class NotRegistered(PenseiveError):
    """Raised when a model is not registered with a site."""
    pass