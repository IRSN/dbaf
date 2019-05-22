from django import template

register = template.Library()

@register.filter
def get_attrs(value, attrs):
    attrs = attrs.split('.')
    ret = value
    for attr in attrs:
        if hasattr(ret, str(attr)):
            ret = getattr(ret, attr)
        elif hasattr(ret, 'has_key') and value.has_key(attr):
            ret = ret[attr]
        elif attr.isdigit() and len(value) > int(attr):
            ret = ret[int(attr)]
    return ret

@register.filter
def get_type(value):
    return type(value).__name__

@register.filter
def format_ifvalue(value, form):
    if value == None or value == "":
        return ""
    else:
        return form.format(value)
