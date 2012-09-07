from foamy.excs import XMLValueError
from foamy.ns import COMMON_NAMESPACES as NS
from foamy.registry import QNameRegistry, NameRegistry
from lxml.etree import Element, SubElement, tostring, fromstring, cleanup_namespaces


class ContextBoundObject(object):
    def __init__(self, context, ns, name):
        self.context = context
        self.ns = ns
        self.name = name
        self.qname = "{%s}%s" % (ns, name)

    def __str__(self):
        return "<%s (%s) at 0x%0x>" % (self.__class__.__name__, self.name, id(self))


class Request(object):
    def __init__(self, url, headers = None, data = None):
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
        ("soap",    NS.tag("soap", "binding")),
        ("soap12",  NS.tag("soap12", "binding")),
        ("http",    NS.tag("http", "binding")),
    )
    def __init__(self, context, ns, name, port_type, binding_options):
        super(Binding, self).__init__(context, ns, name)
        self.port_type = port_type
        self.operation_bindings = {}
        self.binding_options = binding_options

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
        self.operation_bindings[operation] = dict(soap_op.attrib)

    def envelope_message(self, message, operation):
        input_message = operation.input.message
        if len(input_message.parts) > 1:
            raise NotImplementedError("Multi-part messages aren't supported at the moment")
        input_name, input_type = input_message.parts[0]
        message = input_type.marshal(message)

        envelope = Element(NS.tag("soapenv", "Envelope"), nsmap=dict(NS))
        header = SubElement(envelope, NS.tag("soapenv", "Header"))
        body = SubElement(envelope, NS.tag("soapenv", "Body"))
        body.append(message)

        cleanup_namespaces(envelope)
        xml = tostring(envelope, pretty_print=True, encoding="UTF-8", xml_declaration=True)
        opbind = self.operation_bindings[operation]
        req = Request(None, {
            "Content-type": "text/xml; charset=utf-8",
            "SOAPAction": '"%s"' % opbind.get("soapAction")
        }, xml)

        return req

    def unenvelope_message(self, body, operation):
        msg = operation.output.message
        if len(msg.parts) > 1:
            raise NotImplementedError("Multi-part outputs not supported")
        output_name, output_type = msg.parts[0]
        return output_type.unmarshal(body)

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

    def dump(self, dumper):
        for port_name, port in sorted(self.ports.iteritems()):
            dumper.write(str(port))
