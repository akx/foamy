from foamy.excs import XMLValueError
from foamy.ns import COMMON_NAMESPACES as NS
from foamy.registry import QNameRegistry, NameRegistry
from lxml.etree import Element, SubElement, tostring, fromstring, cleanup_namespaces
import logging
logger = logging.getLogger(__name__)


class ContextBoundObject(object):
    def __init__(self, context, ns, name):
        self.context = context
        self.ns = ns
        self.name = name
        self.qname = "{%s}%s" % (ns, name)

    def __str__(self):
        return "<%s (%s) at 0x%0x>" % (self.__class__.__name__, self.name, id(self))


class Request(object):
    def __init__(self, url, headers=None, data=None):
        self.url = url
        self.headers = headers or {}
        self.data = data


class Response(object):
    def __init__(self, request, code, headers, data):
        self.request = request
        self.code = code
        self.headers = headers
        self.data = data


class Binding(ContextBoundObject):
    protocol = None
    usable = False
    protocol_map = (
        ("soap", NS.tag("soap", "binding")),
        ("soap12", NS.tag("soap12", "binding")),
        ("http", NS.tag("http", "binding")),
    )

    def __init__(self, context, ns, name, port_type, binding_options):
        super(Binding, self).__init__(context, ns, name)
        self.port_type = port_type
        self.operation_bindings = {}
        self.binding_options = (binding_options or {})

    @classmethod
    def detect_binding_protocol(cls, binding_tag):
        for protocol, tagname in cls.protocol_map:
            bind_tag = binding_tag.find(tagname)
            if bind_tag is not None:
                return (protocol, dict(bind_tag.attrib))

    def parse_wsdl(self, binding_tag):
        for op_tag in binding_tag.findall(NS.tag("wsdl", "operation")):
            self.parse_wsdl_operation(op_tag)

    def parse_wsdl_operation(self, op_tag):
        pass

    def envelope_message(self, message, operation):
        raise NotImplementedError("Not implemented")

    def unenvelope_message(self, message, operation):
        raise NotImplementedError("Not implemented")


class SOAPBinding(Binding):
    protocol = "soap"
    usable = True

    def parse_wsdl_operation(self, op_tag):
        # XXX: Not complete!
        operation = self.port_type.operations[op_tag.get("name")]
        soap_op = op_tag.find(NS.tag("soap", "operation"))
        if soap_op is None:
            raise XMLValueError("SOAP binding, but no SOAP operation tag.", op_tag)
        default_dict = {"style": self.binding_options.get("style")}
        default_dict.update(soap_op.attrib)
        self.operation_bindings[operation] = default_dict

    def envelope_message(self, message, operation):
        # XXX: `encoded`/`literal` is blissfully ignored
        envelope = Element(NS.tag("soapenv", "Envelope"), nsmap=dict(NS))
        header = SubElement(envelope, NS.tag("soapenv", "Header"))
        body = SubElement(envelope, NS.tag("soapenv", "Body"))

        opbind = self.operation_bindings[operation]
        for el in operation.input.message.marshal(message, style=opbind["style"]):
            body.append(el)

        cleanup_namespaces(envelope)
        xml = tostring(envelope, pretty_print=True, encoding="UTF-8", xml_declaration=True)
        req = Request(None, {
            "Content-type": "text/xml; charset=utf-8",
            "SOAPAction": '"%s"' % opbind.get("soapAction")
        }, xml)

        return req

    def unenvelope_message(self, body, operation):
        opbind = self.operation_bindings[operation]
        return operation.output.message.unmarshal(body, style=opbind["style"])


class OperationPart(object):
    def __init__(self, message):
        self.message = message


class Operation(object):
    def __init__(self, port_type, name):
        self.port_type = port_type
        self.context = port_type.context
        self.name = name
        self.input = None
        self.output = None
        self.faults = []
        self.documentation = None

    def __str__(self):
        return "<Operation %s:%s>" % (self.port_type.name, self.name)

    def _get_signature(self):
        parts = ["("]
        if self.input:
            parts.append(str(self.input.message.name))
        parts.append(")")
        if self.output:
            parts.append(" -> ")
            parts.append(str(self.output.message.name))
        return "".join(parts)

    signature = property(_get_signature)


class PortType(ContextBoundObject):
    def __init__(self, context, ns, name):
        super(PortType, self).__init__(context, ns, name)
        self.operations = NameRegistry()


class Message(ContextBoundObject):
    def __init__(self, context, ns, name):
        super(Message, self).__init__(context, ns, name)
        self.parts = []

    def add_part(self, name, part):
        self.parts.append((name, part))

    def marshal(self, message, style):
        wrapper = Element(self.qname)
        if len(self.parts) > 1:
            self.marshal_multipart(wrapper, message)
        else:
            typename, type = self.parts[0]
            wrapper.append(type.marshal(message))

        if style == "document":  # Document? Okay, just grab the inner nodes then.
            return wrapper.getchildren()
        else:
            return [wrapper]

    def marshal_multipart(self, wrapper, message):
        if not isinstance(message, dict):
            raise TypeError("Input must be dict when marshalling multipart messages (got %r)" % message)

        for name, type in self.parts:
            if name not in message:
                raise ValueError("While marshalling multipart message: Missing part %r" % name)
            subel = SubElement(wrapper, "{%s}%s" % (self.ns, name))
            marshalled = type.marshal(message[name])
            if hasattr(marshalled, "tag"):
                for child in marshalled.getchildren():
                    subel.append(child)
                subel.text = marshalled.text
                marshalled = None
            else:
                subel.text = marshalled
        return wrapper

    def unmarshal(self, message, style):
        if style == "rpc":  # Just simply unwrap the first layer of this XML onion for RPC
            message = message.getchildren()[0]

        if len(self.parts) > 1:
            out = {}
            for name, type in self.parts:
                tag = message.find("{%s}%s" % (self.ns, name))
                out[name] = (type.unmarshal(tag) if tag is not None else None)
            return out
        else:
            typename, type = self.parts[0]
            return type.unmarshal(message)


class Port(object):
    def __init__(self, name, binding, protocol, location):
        self.name = name
        self.binding = binding
        self.protocol = protocol
        self.location = location

    def __str__(self):
        return "<Port '%s' (protocol %s @ %s)>" % (self.name, self.protocol, self.location)

    def envelope_message(self, message, operation):
        request = self.binding.envelope_message(message, operation)
        request.url = self.location
        return request

    def unenvelope_message(self, message, operation):
        tree = fromstring(message)
        body = tree.find(NS.tag("soapenv", "Body"))
        response = self.binding.unenvelope_message(body.getchildren()[0], operation)
        return response


class Service(ContextBoundObject):
    def __init__(self, context, ns, name):
        super(Service, self).__init__(context, ns, name)
        self.ports = NameRegistry()
        self.documentation = None

    def dump(self, dumper):
        for port_name, port in sorted(self.ports.iteritems()):
            dumper.write(str(port))
