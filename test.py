import sys
import logging
logging.basicConfig(level=logging.DEBUG)
from foamy.shortcuts import open_soap
ctx = open_soap("ex/parasoft-calculator.wsdl")
ctx.dump(sys.stdout)
print "==" * 30
srv = ctx.service
print srv.add(x=5, y=5)