from foamy.basic_types import BASIC_TYPES
from foamy.debugging import Dumper
from foamy.loader import ResourceLoader
from foamy.ns import COMMON_NAMESPACES as NS
from foamy.objs import Response
from foamy.registry import QNameRegistry
from foamy.transport import RequestsTransport
from foamy.wsdl import WSDLReader
from lxml.etree import tostring


class WrappedOperation(object):
    def __init__(self, context, port, operation):
        self.context = context
        self.port = port
        self.operation = operation

    def __call__(self, *args, **kwargs):
        if kwargs:
            message = kwargs
        elif args:
            message = args[0]
        else:
            message = None
        return self.context.dispatch(self.port, self.operation, message)


class ServiceSelector(object):
    def __init__(self, context):
        self.context = context
        self.operation_cache = {}
        self.fill_operation_cache()

    def fill_operation_cache(self):
        for service in self.context.services.in_order():
            for port in service.ports.in_order():
                if port.binding.usable:
                    for operation in port.binding.port_type.operations.in_order():
                        self.operation_cache[operation.name] = WrappedOperation(self.context, port, operation)

    def __getattr__(self, op_name):
        res = self.operation_cache.get(op_name)
        if not res:
            raise ValueError("%s is not a known operation in this context." % op_name)
        return res

    def _dump(self, dumper):
        dumper.enter("Known methods:")
        for opname, wop in sorted(self.operation_cache.iteritems()):
            dumper.write(opname + wop.operation.signature)
        dumper.exit()

    def dump(self, stream):
        return self._dump(Dumper(stream))


class Context(object):
    def __init__(self, transport=None, loader=None):
        self.transport = transport or RequestsTransport()
        self.loader = loader or ResourceLoader(self.transport)
        self.types = QNameRegistry()
        self.messages = QNameRegistry()
        self.port_types = QNameRegistry()
        self.bindings = QNameRegistry()
        self.services = QNameRegistry()

    def read_wsdl_from_url(self, url):
        return self.read_wsdl_tree(self.loader.load_xml(url))

    def read_wsdl_tree(self, wsdl_tree):
        reader = WSDLReader(self, wsdl_tree)
        reader.parse()

    def resolve_type(self, qname):
        type = self.types.get(qname) or BASIC_TYPES.get(qname)
        if type:
            return type
        else:
            raise KeyError("Type '%s' is not known to this context." % qname)

    def _dump(self, dumper, with_service=False):
        for kind, source in (
            ("types", self.types),
            ("messages", self.messages),
            ("port types", self.port_types),
            ("bindings", self.bindings),
            ("services", self.services),
        ):
            dumper.enter("Known %s:" % kind)
            for qname, obj in sorted(source.iteritems()):
                dumper.write(qname)
                odump = getattr(obj, "_dump", None)
                if odump:
                    with dumper:
                        odump(dumper)
            dumper.exit()
        if with_service:
            dumper.enter("Service Selector description:")
            self.service._dump(dumper)
            dumper.exit()

    def dump(self, stream, with_service=False):
        return self._dump(Dumper(stream), with_service=with_service)

    def _get_service(self):
        return ServiceSelector(self)

    service = property(_get_service)

    def dispatch(self, port, operation, message):
        req = port.envelope_message(message, operation)
        resp = self.transport.dispatch(req)
        if operation.output:
            resp = port.unenvelope_message(resp.data, operation)
            return resp
        else:
            return
