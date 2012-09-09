from foamy.ns import COMMON_NAMESPACES as NS
from foamy.objs import Binding, SOAPBinding, Message, OperationPart, PortType, Operation, Service, Port
from foamy.types import type_from_xmlschema_element
import logging
logger = logging.getLogger(__name__)


def parse_port_wsdl(port_tag):
    for protocol, tagname in (
        ("soap", NS.tag("soap", "address")),
        ("soap12", NS.tag("soap12", "address")),
        ("http", NS.tag("http", "address")),
    ):
        addr_tag = port_tag.find(tagname)
        if addr_tag is not None:
            return (protocol, addr_tag.get("location"))


class WSDLReader(object):
    BINDING_CLASSES = {
        "soap": SOAPBinding
    }

    def __init__(self, context, wsdl_tree):
        self.context = context
        self.definitions = wsdl_tree.getroot()
        self.nsmap = NS.augment(self.definitions.nsmap)
        assert self.definitions.tag == NS.tag("wsdl", "definitions")
        self.target_namespace = self.definitions.get("targetNamespace")

    def parse(self):
        for types in self.definitions.findall(NS.tag("wsdl", "types")):
            self.parse_types(types)

        for message in self.definitions.findall(NS.tag("wsdl", "message")):
            self.parse_message(message)

        for port_type in self.definitions.findall(NS.tag("wsdl", "portType")):
            self.parse_port_type(port_type)

        for binding in self.definitions.findall(NS.tag("wsdl", "binding")):
            self.parse_binding(binding)

        for service in self.definitions.findall(NS.tag("wsdl", "service")):
            self.parse_service(service)

    def parse_types(self, types):
        for schema in types.findall(NS.tag("schema", "schema")):
            self.parse_xmlschema(schema)

    def parse_xmlschema(self, schema):
        tns = schema.get("targetNamespace")
        self.nsmap = self.nsmap.augment(schema.nsmap)
        # XXX: Always assumes elementFormDefault="qualified"
        new_types = []

        elts = []
        elts.extend(schema.findall(NS.tag("schema", "simpleType")))
        elts.extend(schema.findall(NS.tag("schema", "element")))
        elts.extend(schema.findall(NS.tag("schema", "complexType")))

        for element in elts:
            typeobj = type_from_xmlschema_element(self.nsmap, self.context, tns, element, defer=True)
            self.context.types.register(typeobj)
            new_types.append((typeobj, element))

        for typeobj, element in new_types:
            typeobj.parse_xmlschema_element(self.nsmap, element)

    def parse_message(self, message_tag):
        message = Message(self.context, self.target_namespace, message_tag.get("name"))
        for part_tag in message_tag.findall(NS.tag("wsdl", "part")):
            typename = part_tag.get("element") or part_tag.get("type")
            typename = self.nsmap.to_qname(typename)
            message.add_part(part_tag.get("name"), self.context.resolve_type(typename))
        self.context.messages.register(message)

    def parse_op_part(self, c_tag):
        message = self.nsmap.to_qname(c_tag.get("message"))
        return OperationPart(self.context.messages[message])

    def parse_port_type(self, port_type_tag):
        port_type = PortType(self.context, self.target_namespace, port_type_tag.get("name"))
        for op_tag in port_type_tag.findall(NS.tag("wsdl", "operation")):
            op = Operation(port_type, op_tag.get("name"))
            for c_tag in op_tag.getchildren():
                if c_tag.tag == NS.tag("wsdl", "input"):
                    op.input = self.parse_op_part(c_tag)
                elif c_tag.tag == NS.tag("wsdl", "output"):
                    op.output = self.parse_op_part(c_tag)
                elif c_tag.tag == NS.tag("wsdl", "fault"):
                    op.faults.append(self.parse_op_part(c_tag))
                elif c_tag.tag == NS.tag("wsdl", "documentation"):
                    op.documentation = c_tag.text
                else:
                    raise NotImplementedError("Not implemented: %s" % c_tag.tag)
            port_type.operations.register(op)
        self.context.port_types.register(port_type)

    def parse_binding(self, binding_tag):
        port_type_name = self.nsmap.to_qname(binding_tag.get("type"))
        port_type = self.context.port_types[port_type_name]
        protocol = Binding.detect_binding_protocol(binding_tag)
        binding_name = binding_tag.get("name")

        if not protocol:
            logger.warn("Unable to detect binding protocol, IGNORING binding %s" % binding_name)
            return

        protocol, args = protocol

        binding_cls = self.BINDING_CLASSES.get(protocol, Binding)
        binding = binding_cls(self.context, self.target_namespace, binding_name, port_type, args)
        binding.parse_wsdl(binding_tag)
        self.context.bindings.register(binding)

    def parse_service(self, service_tag):
        service = Service(self.context, self.target_namespace, service_tag.get("name"))
        service.documentation = service_tag.get("documentation")

        for port_tag in service_tag.findall(NS.tag("wsdl", "port")):
            binding_name = self.nsmap.to_qname(port_tag.get("binding"))
            binding = self.context.bindings[binding_name]
            protocol, address = parse_port_wsdl(port_tag)
            port_name = port_tag.get("name")
            if not protocol:
                logger.warn("Unable to detect service %s port %s protocol", service.name, port_name)
            port = Port(port_name, binding, protocol, address)
            service.ports.register(port)
        self.context.services.register(service)
