

def get_user_company_id(user):
    """
    Resolve the company belonging to a non-superadmin user.

    Adjust this helper if your user-to-company relationship uses
    a different field or related name.
    """
    company_id = getattr(user, "company_id", None)

    if company_id:
        return company_id

    employee = getattr(user, "employee", None)
    if employee is not None:
        return getattr(employee, "company_id", None)

    return None


def is_superadmin(user):
    return bool(
        getattr(user, "is_super_admin", False)
        or getattr(user, "is_superadmin", False)
    )

