from django.db.models import Q
from rest_framework.exceptions import NotFound

from quickportal.models import Business, BusinessMembership, BusinessRole


ROLE_RANK = {
    BusinessRole.VIEWER: 1,
    BusinessRole.MANAGER: 2,
    BusinessRole.ADMIN: 3,
}


def accessible_businesses(user, roles=None):
    if user.is_superuser:
        return Business.objects.all()

    memberships = user.business_memberships.all()
    if roles is not None:
        memberships = memberships.filter(role__in=roles)
    business_ids = memberships.values("business_id")
    return Business.objects.filter(
        Q(id__in=business_ids)
        | Q(parent_id__in=business_ids)
        | Q(parent__parent_id__in=business_ids)
    ).distinct()


def get_accessible_business_or_404(user, pk, roles=None):
    try:
        return accessible_businesses(user, roles=roles).select_related("parent").get(pk=pk)
    except (Business.DoesNotExist, TypeError, ValueError) as exc:
        raise NotFound() from exc


def effective_business_role(user, business):
    if user.is_superuser:
        return BusinessRole.ADMIN

    ancestor_ids = [business.id]
    if business.parent_id is not None:
        ancestor_ids.append(business.parent_id)
        if business.parent.parent_id is not None:
            ancestor_ids.append(business.parent.parent_id)

    roles = BusinessMembership.objects.filter(
        user=user, business_id__in=ancestor_ids
    ).values_list("role", flat=True)
    return max(roles, key=lambda role: ROLE_RANK[role], default=None)


def has_business_role(user, business, allowed_roles):
    return effective_business_role(user, business) in allowed_roles


def has_governing_ancestor_admin(business):
    ancestor_ids = []
    if business.parent_id is not None:
        ancestor_ids.append(business.parent_id)
        if business.parent.parent_id is not None:
            ancestor_ids.append(business.parent.parent_id)
    return BusinessMembership.objects.filter(
        business_id__in=ancestor_ids, role=BusinessRole.ADMIN
    ).exists()
