import pytest

from rest_framework.test import APIClient

from user.models import User
from superadmin.models import Company
from finance.category.models import Category


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def company(db):
    return Company.objects.create(
        name="Test Company",
        address="Test Address",
        location="Kerala",
        contact_number="9999999999",
        email="testcompany@example.com",
        modules={},
        amount_per_employee=0,
        initial_payment=0,
        is_active=True,
    )


@pytest.fixture
def second_company(db):
    return Company.objects.create(
        name="Second Company",
        address="Second Address",
        location="Kochi",
        contact_number="8888888888",
        email="secondcompany@example.com",
        modules={},
        amount_per_employee=0,
        initial_payment=0,
        is_active=True,
    )


@pytest.fixture
def hr_admin(db, company):
    return User.objects.create_user(
        username="testhradmin",
        email="hradmin@example.com",
        password="TestPassword123",
        is_hr_admin=True,
        company=company,
        is_active=True,
    )


@pytest.fixture
def employee(db, company):
    return User.objects.create_user(
        username="testemployee",
        email="employee@example.com",
        password="TestPassword123",
        is_employee=True,
        company=company,
        is_active=True,
    )


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def parent_category(company, hr_admin):
    return Category.objects.create(
        company=company,
        code="CAT001",
        category_name="Electronics",
        parent_category=None,
        category_type="product",
        status="active",
        created_by=hr_admin,
    )


@pytest.fixture
def sub_category(company, hr_admin, parent_category):
    return Category.objects.create(
        company=company,
        code="CAT002",
        category_name="Laptop",
        parent_category=parent_category,
        category_type="product",
        status="active",
        created_by=hr_admin,
    )


# ============================================================
# CREATE
# ============================================================

@pytest.mark.django_db
def test_create_parent_category(
    api_client,
    hr_admin,
    company,
):
    api_client.force_authenticate(user=hr_admin)

    data = {
        "code": "CAT100",
        "category_name": "Furniture",
        "parent_category": None,
        "category_type": "product",
        "status": "active",
    }

    response = api_client.post(
        "/api/finance/category/",
        data,
        format="json",
    )

    assert response.status_code == 201

    assert response.data["message"] == (
        "Category created successfully."
    )

    assert Category.objects.filter(
        company=company,
        code="CAT100",
        category_name="Furniture",
    ).exists()


@pytest.mark.django_db
def test_create_sub_category(
    api_client,
    hr_admin,
    company,
    parent_category,
):
    api_client.force_authenticate(user=hr_admin)

    data = {
        "code": "CAT101",
        "category_name": "Chair",
        "parent_category": parent_category.id,
        "category_type": "product",
        "status": "active",
    }

    response = api_client.post(
        "/api/finance/category/",
        data,
        format="json",
    )

    assert response.status_code == 201

    assert Category.objects.filter(
        company=company,
        code="CAT101",
        category_name="Chair",
        parent_category=parent_category,
    ).exists()


# ============================================================
# LIST
# ============================================================

@pytest.mark.django_db
def test_list_categories(
    api_client,
    hr_admin,
    parent_category,
    sub_category,
):
    api_client.force_authenticate(user=hr_admin)

    response = api_client.get(
        "/api/finance/category/"
    )

    assert response.status_code == 200

    assert "results" in response.data

    assert len(response.data["results"]) == 2


# ============================================================
# RETRIEVE
# ============================================================

@pytest.mark.django_db
def test_retrieve_category(
    api_client,
    hr_admin,
    parent_category,
):
    api_client.force_authenticate(user=hr_admin)

    response = api_client.get(
        f"/api/finance/category/{parent_category.id}/"
    )

    assert response.status_code == 200

    assert response.data["message"] == (
        "Category retrieved successfully."
    )

    assert response.data["data"]["id"] == parent_category.id

    assert response.data["data"]["category_name"] == "Electronics"


# ============================================================
# UPDATE
# ============================================================

@pytest.mark.django_db
def test_update_category(
    api_client,
    hr_admin,
    parent_category,
):
    api_client.force_authenticate(user=hr_admin)

    data = {
        "code": "CAT001",
        "category_name": "Electronic Devices",
        "parent_category": None,
        "category_type": "product",
        "status": "active",
    }

    response = api_client.put(
        f"/api/finance/category/{parent_category.id}/",
        data,
        format="json",
    )

    assert response.status_code == 200

    parent_category.refresh_from_db()

    assert parent_category.category_name == "Electronic Devices"


# ============================================================
# PATCH
# ============================================================

@pytest.mark.django_db
def test_patch_category(
    api_client,
    hr_admin,
    parent_category,
):
    api_client.force_authenticate(user=hr_admin)

    data = {
        "status": "inactive"
    }

    response = api_client.patch(
        f"/api/finance/category/{parent_category.id}/",
        data,
        format="json",
    )

    assert response.status_code == 200

    parent_category.refresh_from_db()

    assert parent_category.status == "inactive"


# ============================================================
# DELETE
# ============================================================

@pytest.mark.django_db
def test_delete_category(
    api_client,
    hr_admin,
    parent_category,
):
    api_client.force_authenticate(user=hr_admin)

    category_id = parent_category.id

    response = api_client.delete(
        f"/api/finance/category/{category_id}/"
    )

    assert response.status_code == 200

    assert not Category.objects.filter(
        id=category_id
    ).exists()


# ============================================================
# PARENT CATEGORIES
# ============================================================

@pytest.mark.django_db
def test_get_parent_categories(
    api_client,
    hr_admin,
    parent_category,
    sub_category,
):
    api_client.force_authenticate(user=hr_admin)

    response = api_client.get(
        "/api/finance/category/parents/"
    )

    assert response.status_code == 200

    assert response.data["message"] == (
        "Parent categories retrieved successfully."
    )

    data = response.data["data"]

    assert len(data) == 1

    assert data[0]["category_name"] == "Electronics"


# ============================================================
# SUB-CATEGORIES
# ============================================================

@pytest.mark.django_db
def test_get_sub_categories(
    api_client,
    hr_admin,
    parent_category,
    sub_category,
):
    api_client.force_authenticate(user=hr_admin)

    response = api_client.get(
        f"/api/finance/category/"
        f"{parent_category.id}/subcategories/"
    )

    assert response.status_code == 200

    assert response.data["message"] == (
        "Sub-categories retrieved successfully."
    )

    data = response.data["data"]

    assert len(data) == 1

    assert data[0]["category_name"] == "Laptop"

    assert data[0]["parent_category"] == parent_category.id


# ============================================================
# SUMMARY
# ============================================================

@pytest.mark.django_db
def test_category_summary(
    api_client,
    hr_admin,
    parent_category,
    sub_category,
):
    api_client.force_authenticate(user=hr_admin)

    response = api_client.get(
        "/api/finance/category/summary/"
    )

    assert response.status_code == 200

    assert response.data["message"] == (
        "Category summary retrieved successfully."
    )

    data = response.data["data"]

    assert data["total_categories"] == 2
    assert data["active_categories"] == 2
    assert data["inactive_categories"] == 0
    assert data["parent_categories"] == 1
    assert data["sub_categories"] == 1


# ============================================================
# SEARCH
# ============================================================

@pytest.mark.django_db
def test_search_category(
    api_client,
    hr_admin,
    parent_category,
    sub_category,
):
    api_client.force_authenticate(user=hr_admin)

    response = api_client.get(
        "/api/finance/category/",
        {"search": "Laptop"},
    )

    assert response.status_code == 200

    assert "results" in response.data

    assert len(response.data["results"]) == 1

    assert (
        response.data["results"][0]["category_name"]
        == "Laptop"
    )


# ============================================================
# FILTER - CATEGORY TYPE
# ============================================================

@pytest.mark.django_db
def test_filter_by_category_type(
    api_client,
    hr_admin,
    parent_category,
    sub_category,
):
    api_client.force_authenticate(user=hr_admin)

    response = api_client.get(
        "/api/finance/category/",
        {"category_type": "product"},
    )

    assert response.status_code == 200

    assert "results" in response.data

    assert len(response.data["results"]) == 2

    for category in response.data["results"]:
        assert category["category_type"] == "product"


# ============================================================
# FILTER - STATUS
# ============================================================

@pytest.mark.django_db
def test_filter_by_status(
    api_client,
    hr_admin,
    parent_category,
):
    parent_category.status = "inactive"
    parent_category.save()

    api_client.force_authenticate(user=hr_admin)

    response = api_client.get(
        "/api/finance/category/",
        {"status": "inactive"},
    )

    assert response.status_code == 200

    assert "results" in response.data

    assert len(response.data["results"]) == 1

    assert (
        response.data["results"][0]["status"]
        == "inactive"
    )


# ============================================================
# FILTER - PARENT CATEGORY
# ============================================================

@pytest.mark.django_db
def test_filter_by_parent_category(
    api_client,
    hr_admin,
    parent_category,
    sub_category,
):
    api_client.force_authenticate(user=hr_admin)

    response = api_client.get(
        "/api/finance/category/",
        {
            "parent_category": parent_category.id
        },
    )

    assert response.status_code == 200

    assert "results" in response.data

    assert len(response.data["results"]) == 1

    assert (
        response.data["results"][0]["category_name"]
        == "Laptop"
    )


# ============================================================
# INVALID PARENT
# SUBCATEGORY CANNOT BE PARENT
# ============================================================

@pytest.mark.django_db
def test_subcategory_cannot_be_used_as_parent(
    api_client,
    hr_admin,
    company,
    parent_category,
    sub_category,
):
    api_client.force_authenticate(user=hr_admin)

    data = {
        "code": "CAT200",
        "category_name": "Gaming Laptop",
        "parent_category": sub_category.id,
        "category_type": "product",
        "status": "active",
    }

    response = api_client.post(
        "/api/finance/category/",
        data,
        format="json",
    )

    assert response.status_code == 400

    assert "parent_category" in response.data["errors"]

    assert not Category.objects.filter(
        code="CAT200"
    ).exists()


# ============================================================
# SELF PARENT VALIDATION
# ============================================================

@pytest.mark.django_db
def test_category_cannot_be_its_own_parent(
    api_client,
    hr_admin,
    parent_category,
):
    api_client.force_authenticate(user=hr_admin)

    data = {
        "code": "CAT001",
        "category_name": "Electronics",
        "parent_category": parent_category.id,
        "category_type": "product",
        "status": "active",
    }

    response = api_client.put(
        f"/api/finance/category/{parent_category.id}/",
        data,
        format="json",
    )

    assert response.status_code == 400

    assert "parent_category" in response.data["errors"]


# ============================================================
# CROSS-COMPANY PARENT VALIDATION
# ============================================================

@pytest.mark.django_db
def test_parent_category_must_belong_to_same_company(
    api_client,
    hr_admin,
    company,
    second_company,
):
    api_client.force_authenticate(user=hr_admin)

    other_company_parent = Category.objects.create(
        company=second_company,
        code="OTHER001",
        category_name="Other Electronics",
        parent_category=None,
        category_type="product",
        status="active",
    )

    data = {
        "code": "CAT300",
        "category_name": "Laptop",
        "parent_category": other_company_parent.id,
        "category_type": "product",
        "status": "active",
    }

    response = api_client.post(
        "/api/finance/category/",
        data,
        format="json",
    )

    assert response.status_code == 400

    assert "parent_category" in response.data["errors"]

    assert not Category.objects.filter(
        company=company,
        code="CAT300",
    ).exists()


# ============================================================
# DUPLICATE CODE
# ============================================================

@pytest.mark.django_db
def test_duplicate_category_code(
    api_client,
    hr_admin,
    parent_category,
):
    api_client.force_authenticate(user=hr_admin)

    data = {
        "code": "CAT001",
        "category_name": "Another Category",
        "parent_category": None,
        "category_type": "product",
        "status": "active",
    }

    response = api_client.post(
        "/api/finance/category/",
        data,
        format="json",
    )

    assert response.status_code == 400

    assert "errors" in response.data

    assert "code" in response.data["errors"]

    assert not Category.objects.filter(
        company=parent_category.company,
        category_name="Another Category",
    ).exists()


# ============================================================
# UNAUTHENTICATED USER
# ============================================================

@pytest.mark.django_db
def test_unauthenticated_user_cannot_create_category(
    api_client,
):
    data = {
        "code": "CAT400",
        "category_name": "Unauthorized",
        "parent_category": None,
        "category_type": "product",
        "status": "active",
    }

    response = api_client.post(
        "/api/finance/category/",
        data,
        format="json",
    )

    assert response.status_code in [401, 403]


# ============================================================
# NON HR ADMIN USER
# ============================================================

@pytest.mark.django_db
def test_non_hr_admin_cannot_create_category(
    api_client,
    employee,
):
    api_client.force_authenticate(user=employee)

    data = {
        "code": "CAT500",
        "category_name": "Employee Category",
        "parent_category": None,
        "category_type": "product",
        "status": "active",
    }

    response = api_client.post(
        "/api/finance/category/",
        data,
        format="json",
    )

    assert response.status_code == 403

    assert not Category.objects.filter(
        code="CAT500"
    ).exists()


# ============================================================
# COMPANY ISOLATION
# ============================================================

@pytest.mark.django_db
def test_company_isolation(
    api_client,
    hr_admin,
    company,
    second_company,
):
    Category.objects.create(
        company=company,
        code="MY001",
        category_name="My Company Category",
        parent_category=None,
        category_type="product",
        status="active",
        created_by=hr_admin,
    )

    other_user = User.objects.create_user(
        username="otheradmin",
        email="otheradmin@example.com",
        password="TestPassword123",
        is_hr_admin=True,
        company=second_company,
        is_active=True,
    )

    Category.objects.create(
        company=second_company,
        code="OTHER001",
        category_name="Other Company Category",
        parent_category=None,
        category_type="product",
        status="active",
        created_by=other_user,
    )

    api_client.force_authenticate(user=hr_admin)

    response = api_client.get(
        "/api/finance/category/"
    )

    assert response.status_code == 200

    assert "results" in response.data

    data = response.data["results"]

    assert len(data) == 1

    assert data[0]["category_name"] == (
        "My Company Category"
    )

    assert data[0]["category_name"] != (
        "Other Company Category"
    )