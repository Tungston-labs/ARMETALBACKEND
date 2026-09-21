from rest_framework.pagination import PageNumberPagination

class UnlimitedEmployeePagination(PageNumberPagination):
    page_size = 1000  # or any large number
    page_size_query_param = 'page_size'
    max_page_size = 10000