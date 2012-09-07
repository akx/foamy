from foamy.ns import COMMON_NAMESPACES as NS
from foamy.types import BaseType
import datetime
import decimal

class UnicodeType(BaseType):
    def marshal(self, obj):
        return unicode(obj)
    def unmarshal(self, obj):
        return unicode(obj)

class IntegerType(BaseType):
    def marshal(self, obj):
        return unicode(int(obj))
    def unmarshal(self, obj):
        return int(obj)

class BooleanType(BaseType):
    def marshal(self, obj):
        return ("true" if bool(obj) else "false")
    def unmarshal(self, obj):
        return unicode(obj).lower() == "true"

class FloatType(BaseType):
    def marshal(self, obj):
        return unicode(float(obj))
    def unmarshal(self, obj):
        return float(obj)

class DateType(BaseType):
    def marshal(self, obj):
        return unicode(obj)
    def unmarshal(self, obj):
        return datetime.datetime.strptime("%Y-%m-%d", unicode(obj)).date()

class DecimalType(BaseType):
    def marshal(self, obj):
        return unicode(obj)
    def unmarshal(self, obj):
        return decimal.Decimal(unicode(obj))

BASIC_TYPES = {
    NS.tag("schema", "string"):     UnicodeType(),
    NS.tag("schema", "int"):        IntegerType(),
    NS.tag("schema", "long"):       IntegerType(),
    NS.tag("schema", "boolean"):    BooleanType(),
    NS.tag("schema", "float"):      FloatType(),
    NS.tag("schema", "decimal"):    DecimalType(),
    NS.tag("schema", "date"):       DateType()
}
