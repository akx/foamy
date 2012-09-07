from foamy.loader import ResourceLoader
from foamy.ns import COMMON_NAMESPACES as NS
from foamy.objs import Response
from foamy.registry import QNameRegistry
from foamy.transport import RequestsTransport
from foamy.types import BASE_TYPES
from foamy.wsdl import WSDLReader
from lxml.etree import tostring

class ServiceSelector(object):
    def __init__(self, context):
        self.context = context
        self.operation_cache = {}
        self.fill_operation_cache()

    def fill_operation_cache(self):
        for service in self.context.services.in_order():
            for port in service.ports.in_order():
                if port.binding.usable:
                    for op in port.binding.port_type.operations.in_order():
                        self.operation_cache[op.name] = (port, op)

    def __getattr__(self, op_name):
        res = self.operation_cache.get(op_name)
        if not res:
            raise ValueError("%s is not a known operation in this context." % op_name)
        port, op = res
        def service_func(*args, **kwargs):
            return self.context.dispatch(port, op, args, kwargs)
        return service_func

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
        type = self.types.get(qname) or BASE_TYPES.get(qname)
        if type:
            return type
        else:
            raise KeyError("Type '%s' is not known to this context." % qname)

    def dump(self, stream):
        from foamy.debugging import Dumper
        dumper = Dumper(stream)
        for kind, source in (
            ("types",       self.types),
            ("messages",    self.messages),
            ("port types",  self.port_types),
            ("bindings",    self.bindings),
            ("services",    self.services),
        ):
            dumper.enter("Known %s:" % kind)
            for qname, obj in sorted(source.iteritems()):
                dumper.write(qname)
                odump = getattr(obj, "dump", None)
                if odump:
                    with dumper:
                        odump(dumper)
            dumper.exit()


    def _get_service(self):
        return ServiceSelector(self)

    service = property(_get_service)

    def dispatch(self, port, operation, args, kwargs):
        req = port.envelope_message((kwargs or args), operation)
        resp = self.transport.dispatch(req)
        if operation.output:
            resp = port.unenvelope_message(resp.data, operation)
            return resp
        else:
            return

