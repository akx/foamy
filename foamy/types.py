from foamy.excs import XMLValueError
from foamy.ns import COMMON_NAMESPACES as NS
from foamy.objs import ContextBoundObject
from lxml.etree import Element
import sys
import logging
logger = logging.getLogger(__name__)

class BaseType(object):
    def marshal(self, obj):
        raise NotImplementedError("Not implemented: marshal()")

    def unmarshal(self, node):
        raise NotImplementedError("Not implemented: unmarshal()")

    def craft(self):
        raise NotImplementedError("Not implemented: craft()")

SENTINEL = object()

def read_object_values(obj, keys):
    is_mapping = callable(getattr(obj, "__getitem__", None))
    values = {}
    for key in keys:
        if is_mapping:
            try:
                values[key] = obj[key]
                continue
            except:
                pass
        value = getattr(obj, key, SENTINEL)
        if value is not SENTINEL:
            values[key] = value
    return values

class Type(ContextBoundObject, BaseType):
    def __init__(self, context, ns, name):
        ContextBoundObject.__init__(self, context=context, ns=ns, name=name)
        BaseType.__init__(self)
        self.base = None
        self.nillable = False
        self.min_occurs = 0
        self.max_occurs = 0
        self.attributes = {}

    def parse_xmlschema_element(self, nsmap, element):
        base = element.get("type")
        if base:
            self.base = self.context.resolve_type(nsmap.to_qname(base))
        self.nillable = (element.get("nillable") == "true")
        self.min_occurs = int(element.get("minOccurs", 0))
        max_occurs_str = element.get("maxOccurs", 0)
        if max_occurs_str == "unbounded":
            max_occurs_str = (sys.maxint - 1)
        self.max_occurs = int(max_occurs_str)
        self._read_attributes(nsmap, element)

    def _read_attributes(self, nsmap, element):
        for attr_tag in element.findall(NS.tag("schema", "attribute")):
            attr_name = attr_tag.get("name")
            attr_type = self.context.resolve_type(nsmap.to_qname(attr_tag.get("type")))
            self.attributes[attr_name] = attr_type
            # XXX: May be incomplete?

    def marshal(self, obj):
        logger.debug("Marshalling: %s -> %s", obj, self.name)
        node = Element(self.qname)
        if self.base:
            basic_m = self.base.marshal(obj)
            if basic_m is not None:
                node.text = basic_m
        if self.attributes:
            for key, value in read_object_values(obj, self.attributes).iteritems():
                node.attrib[key] = value
        return node

    def unmarshal(self, node):
        # XXX: This doesn't do anything near the Right Thing, but it does something.
        assert (node.tag == self.qname)
        basic_um = None
        if self.base:
            basic_um = self.base.unmarshal(node.text)
            if not self.attributes and basic_um is not None:
                return basic_um

        out = {}
        for attr_name, attr_type in self.attributes.iteritems():
            out["_%s" % attr_name] = node.attrib.get(attr_name)
        
        if basic_um is not None:
            out["$"] = basic_um

        return out


class ComplexType(Type):
    def parse_xmlschema_element(self, nsmap, element):
        super(ComplexType, self).parse_xmlschema_element(nsmap, element)
        complex_type = element.find(NS.tag("schema", "complexType"))
        sequence = complex_type.find(NS.tag("schema", "sequence"))
        self.sequence = []
        for element in sequence.findall(NS.tag("schema", "element")):
            typeobj = type_from_xmlschema_element(nsmap, self.context, self.ns, element)
            self.sequence.append(typeobj)
        self.sequence_keys = [t.name for t in self.sequence]

    def marshal(self, obj):
        node = Type.marshal(self, obj)
        vals = read_object_values(obj, self.sequence_keys)
        for t in self.sequence:
            if t.name in vals:
                # XXX: Add support for min_occurs, max_occurs, etc.
                node.append(t.marshal(vals[t.name]))
        return node

    def unmarshal(self, node):
        out = Type.unmarshal(self, node)
        for t in self.sequence:
            ttag = node.find(t.qname)
            if ttag is not None:
                out[t.name] = t.unmarshal(ttag)
        return out

class SimpleContentType(Type):
    def parse_xmlschema_element(self, nsmap, element):
        super(SimpleContentType, self).parse_xmlschema_element(nsmap, element)
        simple_content = element.find(NS.tag("schema", "simpleContent"))
        ext_tag = simple_content.find(NS.tag("schema", "extension"))
        if ext_tag is None:
            raise XMLValueError("simpleContent without s:extension...", simple_content)
        base = ext_tag.get("base")
        self.base = self.context.resolve_type(nsmap.to_qname(base))
        self._read_attributes(nsmap, simple_content)

def type_from_xmlschema_element(nsmap, context, tns, element, defer=False):
    complex_type = element.find(NS.tag("schema", "complexType"))
    simple_type = element.find(NS.tag("schema", "simpleType"))
    simple_content = element.find(NS.tag("schema", "simpleContent"))

    if simple_type is not None:
        raise NotImplementedError("simpleType not supported")
    elif simple_content is not None:
        cls = SimpleContentType
    elif complex_type is not None:
        cls = ComplexType
    else:
        cls = Type

    type = cls(context, tns, element.get("name"))
    if not defer:
        type.parse_xmlschema_element(nsmap, element)

    return type