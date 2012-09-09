from foamy.context import Context


def open_soap(wsdl_url, **context_kwargs):
    ctx = Context(**context_kwargs)
    ctx.read_wsdl_from_url(wsdl_url)
    return ctx
