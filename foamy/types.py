# -- encoding: UTF-8 --
from foamy.excs import XMLValueError
from foamy.ns import COMMON_NAMESPACES as NS
from foamy.objs import ContextBoundObject
from foamy.xmlutils import self_or_child
from lxml.etree import Element, tostring
import logging
import sys


logger = logging.getLogger(__name__)
SENTINEL = object()
SIMPLE_CONTENT_TAG = NS.tag("schema", "simpleContent")


class MarshalValueError(ValueError):
    pass


class BaseType(object):
    def marshal(self, obj):
        raise NotImplementedError("Not implemented: marshal()")

    def unmarshal(self, node):
        raise NotImplementedError("Not implemented: unmarshal()")

    def craft(self):
        raise NotImplementedError("Not implemented: craft()")


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
        self.min_occurs = 1
        self.max_occurs = 1
        self.attributes = {}
        self.restriction = None

    def parse_xmlschema_element(self, nsmap, element):
        base = element.get("type")
        if base:
            self.base = self.context.resolve_type(nsmap.to_qname(base))
        self.nillable = (element.get("nillable") == "true")
        self.min_occurs = int(element.get("minOccurs", 1))
        max_occurs_str = element.get("maxOccurs", 1)
        if max_occurs_str == "unbounded":
            max_occurs_str = (sys.maxint - 1)
        self.max_occurs = int(max_occurs_str)
        self._read_attributes(nsmap, element)
        self._read_restriction(nsmap, element)

    def _read_restriction(self, nsmap, element):
        rest_tag = element.find(NS.tag("schema", "restriction"))
        if rest_tag is None:
            return
        rest_base = self.context.resolve_type(nsmap.to_qname(rest_tag.get("base")))
        restriction = []
        for enum_tag in rest_tag.findall(NS.tag("schema", "enumeration")):
            enum_val = rest_base.unmarshal(enum_tag.text or enum_tag.get("value"))
            restriction.append(enum_val)
        self.restriction = restriction
        if not self.base and rest_base:
            self.base = rest_base

    def _read_attributes(self, nsmap, element):
        for attr_tag in element.findall(NS.tag("schema", "attribute")):
            attr_name = attr_tag.get("name")
            attr_type = self.context.resolve_type(nsmap.to_qname(attr_tag.get("type")))
            self.attributes[attr_name] = attr_type
            # XXX: May be incomplete?

    def _get_base_marshal(self, obj):
        if self.base:
            return self.base.marshal(obj)
        else:
            logger.debug("[%s] Base marshal: value %r *** NO BASE", self, obj)

    def marshal(self, obj):
        node = Element(self.qname)
        if self.base:
            node.text = self._get_base_marshal(obj)
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


class TypeList(object):
    def __init__(self, parent, types):
        self.parent = parent
        self.content = list(types)
        self.keys = sorted(set(t.name for t in self.content))

    def __iter__(self):
        return iter(self.content)

    def marshal(self, obj, always_allow_multiple=False):
        if isinstance(obj, (list, tuple)) and len(obj) == len(self.keys):
            vals = dict(zip(self.keys, obj))
        else:
            vals = read_object_values(obj, self.keys)

        for t in self:
            if t.name in vals:
                val = vals[t.name]
                if not isinstance(val, (list, tuple)):
                    val = (val,)
                if not always_allow_multiple and len(val) > t.max_occurs:
                    raise MarshalValueError("%s:%s has max_occurs %d, but got %d values" % (self.parent, t.name, t.max_occurs, len(val)))
                if len(val) < t.min_occurs:
                    raise MarshalValueError("%s:%s has min_occurs %d, but got %d values" % (self.parent, t.name, t.min_occurs, len(val)))

                for sval in val:
                    yield t.marshal(sval)
            else:
                if t.nillable:
                    yield t.marshal(None)
                    continue
                if t.min_occurs > 0:
                    raise MarshalValueError("Value %s:%s is required (min_occurs %d), but no value could be found." % (self.parent, t.name, t.min_occurs))


class BaseComplexType(Type):
    def parse_type_list(self, nsmap, list_el):
        lst = []
        for element in list_el.findall(NS.tag("schema", "element")):
            typeobj = type_from_xmlschema_element(nsmap, self.context, self.ns, element)
            lst.append(typeobj)
        return TypeList(self, lst)


class ComplexSequenceType(BaseComplexType):
    def parse_xmlschema_element(self, nsmap, element):
        super(ComplexSequenceType, self).parse_xmlschema_element(nsmap, element)
        complex_type = self_or_child(element, NS.tag("schema", "complexType"))
        self.sequence = self.parse_type_list(nsmap, complex_type.find(NS.tag("schema", "sequence")))

    def marshal(self, obj):
        out = BaseComplexType.marshal(self, obj)
        for el in self.sequence.marshal(obj):
            out.append(el)
        return out

    def unmarshal(self, node):
        out = BaseComplexType.unmarshal(self, node)
        for t in self.sequence:
            ttag = node.find(t.qname)
            if ttag is not None:
                out[t.name] = t.unmarshal(ttag)
        return out


class ComplexAllType(BaseComplexType):
    def parse_xmlschema_element(self, nsmap, element):
        super(ComplexAllType, self).parse_xmlschema_element(nsmap, element)
        complex_type = self_or_child(element, NS.tag("schema", "complexType"))
        self.all = self.parse_type_list(nsmap, complex_type.find(NS.tag("schema", "all")))
        for type in self.all:
            type.min_occurs = 0

    def marshal(self, obj):
        out = BaseComplexType.marshal(self, obj)

        if hasattr(obj, "keys"):
            obj_keys = set(obj.keys())
            allowed_keys = set(self.all.keys)
            in_obj_not_allowed = (obj_keys - allowed_keys)
            if in_obj_not_allowed:
                raise ValueError("ComplexAllType marshalling: Object %r has extraneous keys (%r)" % (obj, sorted(in_obj_not_allowed)))

        for el in self.all.marshal(obj, True):
            out.append(el)
        return out

    def unmarshal(self, obj):
        raise NotImplementedError("Not implemented: ComplexAllType.unmarshal()")


class SimpleContentType(Type):
    def parse_xmlschema_element(self, nsmap, element):
        super(SimpleContentType, self).parse_xmlschema_element(nsmap, element)
        simple_content = self_or_child(element, SIMPLE_CONTENT_TAG)
        ext_tag = simple_content.find(NS.tag("schema", "extension"))
        if ext_tag is None:
            raise XMLValueError("simpleContent without s:extension...", simple_content)
        base = ext_tag.get("base")
        self.base = self.context.resolve_type(nsmap.to_qname(base))
        self._read_attributes(nsmap, simple_content)


class SimpleType(Type):
    def parse_xmlschema_element(self, nsmap, element):
        super(SimpleType, self).parse_xmlschema_element(nsmap, element)
        if element.find(NS.tag("schema", "union")) is not None:
            raise NotImplementedError("Not implemented: unions")
        if element.find(NS.tag("schema", "list")) is not None:
            raise NotImplementedError("Not implemented: lists")

    def marshal(self, obj):
        return self._get_base_marshal(obj)

    def unmarshal(self, obj):
        raise NotImplementedError("Not implemented: SimpleType::unmarshal")


def type_from_xmlschema_element(nsmap, context, tns, element, defer=False):
    complex_type = self_or_child(element, NS.tag("schema", "complexType"))
    simple_type = self_or_child(element, NS.tag("schema", "simpleType"))
    simple_content = self_or_child(element, SIMPLE_CONTENT_TAG)

    if simple_type is not None:
        cls = SimpleType
    elif simple_content is not None:
        cls = SimpleContentType
    elif complex_type is not None:
        if complex_type.find(NS.tag("schema", "all")) is not None:
            cls = ComplexAllType
        elif complex_type.find(NS.tag("schema", "sequence")) is not None:
            cls = ComplexSequenceType
        else:
            raise ValueError("Unparsable complexType!")
    else:
        cls = Type

    #logger.debug("%s -> %s", element, cls)

    type = cls(context, tns, element.get("name"))
    if not defer:
        nsmap = nsmap.augment(element.nsmap)
        type.parse_xmlschema_element(nsmap, element)

    return type
