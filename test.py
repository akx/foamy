import sys
import logging
import datetime
DEBUG = ("-d" in sys.argv[1:])
from foamy.shortcuts import open_soap

if DEBUG:
	logging.basicConfig(level=logging.DEBUG)

def test_wsdl(wsdl):
	ctx = open_soap(wsdl)
	if DEBUG:
		ctx.dump(sys.stdout, True)
		print "==" * 30
	return ctx.service

def test_cc():
	cc = test_wsdl("ex/currencyconvertor.wsdl")
	cr = cc.ConversionRate({"FromCurrency": "EUR", "ToCurrency": "USD"})
	print "EUR -> USD: %s" % cr["ConversionRateResult"]


def test_ndfd():
	cc = test_wsdl("ex/ndfdXML.wsdl")
	endTime = datetime.datetime(2016, 9, 9)
	startTime = datetime.datetime(2012, 1, 1)
	wd = cc.NDFDgen(latitude=39, longitude=-77, product="time-series", startTime=startTime, endTime=endTime, Unit="m", weatherParameters={"maxt": True})
	print "Weather data: %d bytes of XML" % len(wd)


def test_calculator():
	cc = test_wsdl("ex/parasoft-calculator.wsdl")
	cr = cc.multiply((64, 32))
	print "64 * 32 = %s" % cr["Result"]


if __name__ == '__main__':
	test_cc()
	test_ndfd()
	test_calculator()