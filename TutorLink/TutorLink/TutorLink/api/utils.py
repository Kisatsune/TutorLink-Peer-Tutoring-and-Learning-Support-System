
import xml.etree.ElementTree as ET
from functools import wraps

from django.http import HttpResponse, QueryDict


def to_xml_response(root, status=200):
    body = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return HttpResponse(body, status=status, content_type="application/xml; charset=utf-8")


def add_text(parent, tag, value):
    """Add <tag>value</tag> under parent (None becomes an empty element)."""
    element = ET.SubElement(parent, tag)
    element.text = "" if value is None else str(value)
    return element


def message_response(text, status=200):
    root = ET.Element("message")
    root.text = text
    return to_xml_response(root, status)


def error_response(text, status=400):
    root = ET.Element("error")
    root.set("status", str(status))
    root.text = text
    return to_xml_response(root, status)


def form_errors_response(form):
    """Turn Django form validation errors into <errors><error field="...">text</error></errors>."""
    root = ET.Element("errors")
    for field, messages in form.errors.items():
        for text in messages:
            error = ET.SubElement(root, "error")
            error.set("field", field)
            error.text = str(text)
    return to_xml_response(root, 400)


def methods(*allowed):
    """Reject other HTTP methods with an XML error (instead of Django's empty 405 page)."""

    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if request.method not in allowed:
                return error_response("Method not allowed.", 405)
            return view(request, *args, **kwargs)

        return wrapped

    return decorator


def get_data(request):
    """Form data for POST and PUT requests (Django only parses POST bodies by itself)."""
    if request.method == "POST":
        return request.POST
    return QueryDict(request.body, encoding="utf-8")
