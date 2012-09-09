from foamy.ns import COMMON_NAMESPACES as NS
from foamy.types import BaseType
import datetime
import decimal
import foamy.iso8601 as iso8601


def unwrap(obj):
    if hasattr(obj, "tag") and hasattr(obj, "text"):
        return (obj.text or "")
    else:
        return obj


class UnicodeType(BaseType):
    def marshal(self, obj):
        return unicode(obj)

    def unmarshal(self, obj):
        return unicode(unwrap(obj))

    def craft(self):
        return ""


class IntegerType(BaseType):
    def marshal(self, obj):
        return unicode(int(obj))

    def unmarshal(self, obj):
        return int(unwrap(obj))

    def craft(self):
        return 0


class LongType(IntegerType):
    pass


class BooleanType(BaseType):
    def marshal(self, obj):
        return ("true" if bool(obj) else "false")

    def unmarshal(self, obj):
        return unicode(unwrap(obj)).lower() == "true"

    def craft(self):
        return False


class FloatType(BaseType):
    def marshal(self, obj):
        return unicode(float(obj))

    def unmarshal(self, obj):
        return float(unwrap(obj))

    def craft(self):
        return 0.0


class DoubleType(FloatType):
    pass


class DateType(BaseType):
    def marshal(self, obj):
        return obj.strftime("%Y-%m-%d")

    def unmarshal(self, obj):
        return datetime.datetime.strptime("%Y-%m-%d", unicode(unwrap(obj))).date()

    def craft(self):
        return datetime.date(1970, 1, 1)


class DateTimeType(BaseType):
    def marshal(self, obj):
        return obj.isoformat("T")

    def unmarshal(self, obj):
        return iso8601.parse_date(unicode(unwrap(obj)))

    def craft(self):
        return datetime.datetime(1970, 1, 1, 0, 0, 0)


class DecimalType(BaseType):
    def marshal(self, obj):
        return unicode(obj)

    def unmarshal(self, obj):
        return decimal.Decimal(unicode(unwrap(obj)))

    def craft(self):
        return decimal.Decimal(0)


BASIC_TYPES = {
    NS.tag("schema", "string"): UnicodeType(),
    NS.tag("schema", "int"): IntegerType(),
    NS.tag("schema", "integer"): IntegerType(),
    NS.tag("schema", "long"): LongType(),
    NS.tag("schema", "boolean"): BooleanType(),
    NS.tag("schema", "float"): FloatType(),
    NS.tag("schema", "double"): DoubleType(),
    NS.tag("schema", "decimal"): DecimalType(),
    NS.tag("schema", "date"): DateType(),
    NS.tag("schema", "dateTime"): DateTimeType()
}
