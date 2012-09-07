class Registry(dict):
    KEY_ATTRIBUTE = "identifier"
    def __init__(self, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)
        self.registration_order = []

    def register(self, obj):
        key = getattr(obj, self.KEY_ATTRIBUTE)
        if key not in self:
            self[key] = obj
            self.registration_order.append(key)

    def in_order(self):
        return (self[key] for key in self.registration_order)

class QNameRegistry(Registry):
    KEY_ATTRIBUTE = "qname"

class NameRegistry(Registry):
    KEY_ATTRIBUTE = "name"