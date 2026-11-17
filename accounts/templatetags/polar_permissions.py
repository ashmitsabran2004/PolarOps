from django import template
from accounts.permissions import can

register = template.Library()


@register.simple_tag(takes_context=True)
def perms_can(context, action, obj=None):
    request = context.get('request')
    return bool(request and can(request.user, action, obj))
