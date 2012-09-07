class NamespaceMap(dict):
    def __init__(self, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)
        self.reverse = dict((url, name) for (name, url) in self.iteritems())

    def __getattr__(self, key):
        if key in self:
            return self[key]
        return dict.__getattribute__(self, key)

    def tag(self, ns, tag):
        return "{%s}%s" % (self[ns], tag)

    def augment(self, *args, **kwargs):
        dct = dict(self, **kwargs)
        for arg in args:
            dct.update(arg)
        return self.__class__(dct)

    def to_qname(self, cname):
        ns, name = cname.rsplit(":", 1)
        return self.tag(ns, name)

COMMON_NAMESPACES = NamespaceMap(
    http="http://schemas.xmlsoap.org/wsdl/http/",
    mime="http://schemas.xmlsoap.org/wsdl/mime/",
    msc="http://schemas.microsoft.com/ws/2005/12/wsdl/contract",
    schema="http://www.w3.org/2001/XMLSchema",
    soap12="http://schemas.xmlsoap.org/wsdl/soap12/",
    soap="http://schemas.xmlsoap.org/wsdl/soap/",
    soapenv="http://schemas.xmlsoap.org/soap/envelope/",
    soapenc="http://schemas.xmlsoap.org/soap/encoding/",
    tm="http://microsoft.com/wsdl/mime/textMatching/",
    wsa10="http://www.w3.org/2005/08/addressing",
    wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing",
    wsap="http://schemas.xmlsoap.org/ws/2004/08/addressing/policy",
    wsaw="http://www.w3.org/2006/05/addressing/wsdl",
    wsdl="http://schemas.xmlsoap.org/wsdl/",
    wsp="http://schemas.xmlsoap.org/ws/2004/09/policy",
    wssu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd",
    wsx="http://schemas.xmlsoap.org/ws/2004/09/mex",
)