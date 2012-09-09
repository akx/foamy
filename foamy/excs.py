from lxml.etree import tostring


class XMLValueError(ValueError):
    def __init__(self, message, node):
        self.node = node
        ValueError.__init__(self, message)

    def __str__(self):
        return "%s [\n%s\n]" % (self.message, tostring(self.node, pretty_print=True))
