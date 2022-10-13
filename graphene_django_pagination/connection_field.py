import re
import math

from graphene import Int, String
from graphene_django.filter import DjangoFilterConnectionField
from graphene_django.utils import maybe_queryset
from django.core.paginator import Paginator
from django.db.models.query import QuerySet

from . import PaginationConnection, PageInfoExtra
from django import __version__ as django_version


class DjangoPaginationConnectionField(DjangoFilterConnectionField):
    def __init__(
        self,
        type,
        fields=None,
        extra_filter_meta=None,
        filterset_class=None,
        *args,
        **kwargs,
    ):
        self._type = type
        self._fields = fields
        self._provided_filterset_class = filterset_class
        self._filterset_class = None
        self._extra_filter_meta = extra_filter_meta
        self._base_args = None

        kwargs.setdefault("limit", Int(description="Query limit"))
        kwargs.setdefault("offset", Int(description="Query offset"))

        super().__init__(type, *args, **kwargs)

    @property
    def type(self):
        class NodeConnection(PaginationConnection):
            total_count = Int()

            class Meta:
                node = self._type
                name = f"{self._type._meta.name}NodeConnection"

            def resolve_total_count(self, info, **kwargs):
                try:
                    return self.length
                except AttributeError:
                    try:
                        return self.iterable.count()
                    except AttributeError:
                        return len(list(self.iterable))

        return NodeConnection

    @classmethod
    def resolve_connection(cls, connection, arguments, iterable, *args, **kwargs):
        iterable = maybe_queryset(iterable)

        connection = connection_from_list_slice(
            iterable,
            arguments,
            connection_type=connection,
            pageinfo_type=PageInfoExtra,
        )
        connection.iterable = iterable

        return connection


def connection_from_list_slice(
    list_slice, args=None, connection_type=None, pageinfo_type=None
):
    args = args or {}
    limit = args.get("limit", None)
    offset = args.get("offset", 0)

    if limit is None:
        return connection_type(
            results=list_slice,
            page_info=pageinfo_type(has_previous_page=False, has_next_page=False),
        )
    assert isinstance(limit, int), "Limit must be of type int"
    assert limit > 0, "Limit must be positive integer greater than 0"

    paginator = Paginator(list_slice, limit)
    _slice = list_slice[offset : (offset + limit)]

    page_num = math.ceil(offset / limit) + 1
    page_num = paginator.num_pages if page_num > paginator.num_pages else page_num
    page = paginator.page(page_num)

    conn = connection_type(
        results=_slice,
        page_info=pageinfo_type(
            has_previous_page=page.has_previous(), has_next_page=page.has_next()
        ),
    )
    conn.length = paginator.count
    return conn
