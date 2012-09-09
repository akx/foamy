from foamy.objs import Response
import logging
import requests
logger = logging.getLogger(__name__)


class RequestsTransport(object):
    def __init__(self):
        self.session = requests.session()

    def dispatch(self, request):
        kw = {"url": request.url, "headers": request.headers}
        if request.data:
            kw["method"] = "POST"
            kw["data"] = request.data
        else:
            kw["method"] = "GET"

        logger.debug("DISPATCHING: %s -> %s: %s", kw["method"], kw["url"], kw.get("data", ""))

        resp = self.session.request(**kw)
        resp.raise_for_status()

        return Response(request, resp.status_code, resp.headers, resp.content)
