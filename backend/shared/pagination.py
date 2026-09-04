from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
import math

class CustomPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response({
            'total_items': self.page.paginator.count,
            'total_pages': math.ceil(self.page.paginator.count / self.page.paginator.per_page),
            'current_page': self.page.number,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data,
        })

class HourlyLocationLogPagination(PageNumberPagination):
    page_size = 100          # Default logs per page
    page_size_query_param = "page_size"  # Allow custom page size via query param
    max_page_size = 500