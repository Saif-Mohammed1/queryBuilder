from __future__ import annotations
from typing import Dict, List, Optional, Any, Union, Type
import asyncio
import re
import logging

from sqlalchemy import or_, desc, asc, text, func, select
from sqlalchemy.orm import Query, Session
from sqlalchemy.ext.asyncio import AsyncSession

# --- Your local project imports ---
from .queryBuilder_types import (
    QueryBuilderConfig,
    QueryBuilderResult,
    PaginationMeta,
    JoinConfig,
    JoinType,
    Operator,
    QueryBuilderError,
)

logger = logging.getLogger(__name__)


class QueryBuilder:
    """
    Python equivalent of TypeScript QueryBuilder for SQLAlchemy

    Usage example (sync Flask-SQLAlchemy session shown):

        qb = QueryBuilder(
            session=db.session,
            model=ProductModel,
            query_params={'category': 'electronics', 'page': '2', 'limit': '10'},
            config=QueryBuilderConfig(
                allowed_filters=['name', 'category', 'price', 'active'],
                allowed_sorts=['name', 'price', 'created_at'],
                max_limit=50,
                enable_full_text_search=True,
                search_fields=['name', 'description'],
            ),
        )
        result = await qb.execute()

    Notes
    -----
    * This class supports **sync SQLAlchemy sessions** (typical Flask-SQLAlchemy) in a
      non-blocking way for asyncio by using `asyncio.to_thread(...)`.
    * The **AsyncSession** code-path is currently not implemented; a clear error is
      raised to avoid silent misuse. If you need native async DB access, migrate the
      builders to construct Core `select(...)` statements and execute them with
      `AsyncSession`.
    """

    def __init__(
        self,
        session: Union[Session, AsyncSession],
        model: Type,
        query_params: Dict[str, Any],
        config: QueryBuilderConfig,
        is_aggregate_enabled: bool = False,
    ):
        self.session = session
        self.model = model
        self.table_name = getattr(model, "__tablename__", model.__name__)
        self.config = config
        self.is_aggregate_enabled = is_aggregate_enabled
        self.is_async_session = isinstance(session, AsyncSession)

        # Parse/sanitize query parameters
        self.original_params = self._normalize_params(query_params)
        self._sanitize_input()

        # Initialize query components (sync ORM Query only)
        # NOTE: AsyncSession does not expose .query; we don't build it for async path.
        self.query: Optional[Query] = None
        if not self.is_async_session:
            # type: ignore[attr-defined]
            self.query = session.query(model)  # Flask-SQLAlchemy style

        self.joins: List[JoinConfig] = []
        self.total_count: Optional[int] = None

        # Pagination defaults
        self.page: int = 1
        self.limit: int = config.max_limit
        self.filters: Dict[str, Any] = {}

    # -----------------------
    # Param helpers
    # -----------------------
    def _normalize_params(self, params: Dict[str, Any]) -> Dict[str, str]:
        """Normalize query parameters to string values."""
        normalized: Dict[str, str] = {}
        for key, value in params.items():
            if isinstance(value, list):
                normalized[key] = ",".join(str(v) for v in value)
            else:
                normalized[key] = str(value) if value is not None else ""
        return normalized

    def _sanitize_input(self) -> None:
        """Keep only valid/whitelisted parameters."""
        valid_params: Dict[str, str] = {}
        for key, value in self.original_params.items():
            if value and self._is_valid_param(key):
                valid_params[key] = value
        self.original_params = valid_params

    def _is_valid_param(self, key: str) -> bool:
        # Standard parameters always allowed
        if key in ["page", "limit", "sort", "search", "fields"]:
            return True

        # Extract base key (remove operators like [gt], [in])
        base_key = re.sub(r"\[.*\]", "", key)

        # Apply alias mapping
        aliased_key = self.config.param_aliases.get(base_key, base_key)
        db_field = self.config.filter_map.get(aliased_key, aliased_key)

        # Remove table prefix if present and matches current table
        if isinstance(db_field, str) and "." in db_field:
            prefix, col = db_field.split(".", 1)
            if prefix == self.table_name:
                db_field = col

        return db_field in self.config.allowed_filters

    def _parse_value(self, value: str) -> Any:
        if "," in value:
            return [self._parse_value(v.strip()) for v in value.split(",")]
        if re.match(r"^\d+$", value):
            return int(value)
        if re.match(r"^\d+\.\d+$", value):
            return float(value)
        vl = value.lower()
        if vl == "true":
            return True
        if vl == "false":
            return False
        return value

    # -----------------------
    # Query build steps (sync path)
    # -----------------------
    def join(self, join_config: JoinConfig) -> "QueryBuilder":
        self.joins.append(join_config)
        return self

    def _apply_joins(self) -> "QueryBuilder":
        if self.query is None:
            # joins currently only supported for sync .query path
            return self
        for join_config in self.joins:
            alias = join_config.alias or join_config.table
            join_table = f"{join_config.table} AS {alias}"
            right_column = f"{alias}.{join_config.on_right}"

            cond = text(f"{self.table_name}.{join_config.on_left} = {right_column}")
            if join_config.type == JoinType.INNER:
                self.query = self.query.join(text(join_table), cond)
            elif join_config.type == JoinType.LEFT:
                self.query = self.query.outerjoin(text(join_table), cond)
            # (other join types can be added here)
        return self

    def _build_filter(self) -> "QueryBuilder":
        if self.query is None:
            return self
        where_clauses: Dict[str, Any] = {}

        for key, value in self.original_params.items():
            m = re.match(r"(\w+)\[(\w+)\]", key)
            if m:
                base_key, operator = m.groups()
            else:
                base_key, operator = key, None

            if base_key in ["page", "limit", "sort", "fields", "search"]:
                continue

            if base_key == "search":
                self._handle_text_search(value)
                continue

            if base_key in self.config.fixed_filters:
                continue

            aliased_key = self.config.param_aliases.get(base_key, base_key)
            db_field = self.config.filter_map.get(aliased_key, aliased_key)
            field_name = db_field.split(".")[-1] if "." in db_field else db_field

            if field_name not in self.config.allowed_filters:
                continue

            parsed_value = self._parse_value(value)

            if hasattr(self.model, field_name):
                column = getattr(self.model, field_name)
            else:
                continue

            if operator:
                self._apply_operator(column, operator, parsed_value)
            else:
                where_clauses[field_name] = parsed_value

        if where_clauses:
            self.query = self.query.filter_by(**where_clauses)

        if self.config.fixed_filters:
            for field, value in self.config.fixed_filters.items():
                if hasattr(self.model, field):
                    column = getattr(self.model, field)
                    self.query = self.query.filter(column == value)

        return self

    def _apply_operator(self, column, operator: str, value: Any) -> None:
        try:
            if operator == "gt":
                self.query = self.query.filter(column > value)
            elif operator == "gte":
                self.query = self.query.filter(column >= value)
            elif operator == "lt":
                self.query = self.query.filter(column < value)
            elif operator == "lte":
                self.query = self.query.filter(column <= value)
            elif operator == "ne":
                self.query = self.query.filter(column != value)
            elif operator == "in":
                if isinstance(value, list):
                    self.query = self.query.filter(column.in_(value))
                else:
                    logger.warning("IN operator requires list value, got: %s", type(value))
            elif operator == "nin":
                if isinstance(value, list):
                    self.query = self.query.filter(~column.in_(value))
                else:
                    logger.warning("NOT IN operator requires list value, got: %s", type(value))
            elif operator == "li":
                self.query = self.query.filter(column.like(f"%{value}%"))
            elif operator == "ili":
                self.query = self.query.filter(column.ilike(f"%{value}%"))
            elif operator == "con":
                # PostgreSQL JSONB contains operator
                self.query = self.query.filter(column.op("@>")(value))
            else:
                logger.warning("Unsupported operator: %s", operator)
        except Exception as e:
            logger.error("Error applying operator %s: %s", operator, str(e))

    def _handle_text_search(self, search_term: str) -> None:
        if self.query is None:
            return
        if not self.config.enable_full_text_search or not self.config.search_fields:
            return
        conditions = []
        for field in self.config.search_fields:
            if hasattr(self.model, field):
                column = getattr(self.model, field)
                conditions.append(column.ilike(f"%{search_term}%"))
        if conditions:
            self.query = self.query.filter(or_(*conditions))

    def _build_sort(self) -> "QueryBuilder":
        if self.query is None:
            return self
        sort_param = self.original_params.get("sort", self.config.default_sort)
        if not sort_param:
            return self
        sorts = [s.strip() for s in sort_param.split(",")]
        for sort_item in sorts:
            if sort_item.startswith("-"):
                field, direction = sort_item[1:], "desc"
            else:
                field, direction = sort_item, "asc"

            if ":" in field:
                field, direction = field.split(":", 1)

            db_field = self.config.filter_map.get(field, field)
            if db_field in self.config.allowed_sorts and hasattr(self.model, db_field):
                column = getattr(self.model, db_field)
                self.query = self.query.order_by(desc(column) if direction.lower() == "desc" else asc(column))
        return self

    def _build_pagination(self) -> "QueryBuilder":
        self.page = max(1, int(self.original_params.get("page", 1)))
        self.limit = min(self.config.max_limit, int(self.original_params.get("limit", self.config.max_limit)))
        return self

    def _build_projection(self) -> "QueryBuilder":
        if self.query is None:
            return self
        # Field selection
        if "fields" in self.original_params:
            fields = [f.strip() for f in self.original_params["fields"].split(",")]
            select_fields = []
            for field in fields:
                mapped_field = self.config.filter_map.get(field, field)
                if mapped_field in self.config.allowed_filters and hasattr(self.model, mapped_field):
                    if field in self.config.date_format_fields:
                        date_format = self.config.date_format_fields[field]
                        column = getattr(self.model, mapped_field)
                        formatted = func.to_char(column, date_format).label(field)
                        select_fields.append(formatted)
                    else:
                        select_fields.append(getattr(self.model, mapped_field))
            if select_fields:
                self.query = self.query.with_entities(*select_fields)
        elif self.config.select_fields:
            select_fields = []
            for field in self.config.select_fields:
                if hasattr(self.model, field):
                    if field in self.config.date_format_fields:
                        date_format = self.config.date_format_fields[field]
                        column = getattr(self.model, field)
                        formatted = func.to_char(column, date_format).label(field)
                        select_fields.append(formatted)
                    else:
                        select_fields.append(getattr(self.model, field))
            if select_fields:
                self.query = self.query.with_entities(*select_fields)
        return self

    # -----------------------
    # Execute
    # -----------------------
    async def execute(self) -> QueryBuilderResult:
        try:
            # Build the (sync) query parts
            self._apply_joins()
            self._build_filter()
            self._build_sort()
            self._build_pagination()
            self._build_projection()

            if self.is_async_session:
                # If you need native async, implement builders that produce a Core
                # `select(...)` and execute with the AsyncSession here.
                raise NotImplementedError(
                    "AsyncSession path is not implemented yet. Use a sync Session with to_thread, "
                    "or migrate builders to Core select() statements for full async."
                )

            # --- Sync Session path, executed off the event loop thread ---
            from flask import current_app

            app = current_app._get_current_object()

            def _data_with_ctx() -> List[Any]:
                with app.app_context():
                    return self._execute_data_query_sync()

            def _count_with_ctx() -> int:
                with app.app_context():
                    return self._execute_count_query_sync()

            data, total = await asyncio.gather(
                asyncio.to_thread(_data_with_ctx),
                asyncio.to_thread(_count_with_ctx),
            )

            total_pages = (total + self.limit - 1) // self.limit
            meta = PaginationMeta(
                total=total,
                page=self.page,
                limit=self.limit,
                total_pages=total_pages,
                has_next=self.page < total_pages,
                has_prev=self.page > 1,
            )

            return QueryBuilderResult(
                docs=data,
                meta=meta,
                links=self._build_links(total_pages),
            )

        except Exception as error:
            logger.exception("QueryBuilder Error: %s", str(error))
            raise QueryBuilderError("Failed to execute query", error)

    # -----------------------
    # Sync execution helpers
    # -----------------------
    def _execute_data_query_sync(self) -> List[Any]:
        assert self.query is not None, "Sync session expected"
        paginated = self.query.offset((self.page - 1) * self.limit).limit(self.limit)
        return paginated.all()

    def _execute_count_query_sync(self) -> int:
        assert self.query is not None, "Sync session expected"
        # Robust count: wrap the filtered, de-ordered query as a subquery and count rows
        base_subq = self.query.order_by(None).subquery()
        stmt = select(func.count()).select_from(base_subq)
        return int(self.session.execute(stmt).scalar() or 0)

    # -----------------------
    # Links
    # -----------------------
    def _build_links(self, total_pages: int) -> Dict[str, str]:
        links: Dict[str, str] = {}
        params = dict(self.original_params)

        # Remove excluded fields
        for field in self.config.exclude_links_fields:
            params.pop(field, None)

        link_configs = {
            "first": 1,
            "prev": self.page - 1,
            "next": self.page + 1,
            "last": total_pages,
        }

        for rel, page_num in link_configs.items():
            if (
                (rel == "prev" and self.page > 1)
                or (rel == "next" and self.page < total_pages)
                or rel in ["first", "last"]
            ):
                params["page"] = str(page_num)
                query_string = "&".join([f"{k}={v}" for k, v in params.items()])
                links[rel] = f"?{query_string}"

        return links

    # -----------------------
    # Async execution helpers (not implemented)
    # -----------------------
    async def _execute_data_query_async(self) -> List[Any]:
        raise NotImplementedError("AsyncSession not yet implemented")

    async def _execute_count_query_async(self) -> int:
        raise NotImplementedError("AsyncSession not yet implemented")


# -----------------------------------------------------------------------------
# Example repository wiring (unchanged public interface, non-blocking under async)
# -----------------------------------------------------------------------------
from .base_repository import BaseRepository
from app.models import ProductModel, PublicProductsViewModel
from app.lib.utilities.query_builder import QueryBuilder as _QB  # if placed elsewhere
from app.lib.types.query_builder_types import QueryBuilderConfig as _QBConfig
from app import db


class ProductsRepository(BaseRepository):
    def __init__(self):
        super().__init__(ProductModel)

    async def get_products(self, query_params: Optional[Dict[str, Any]] = None):
        """Get products using QueryBuilder utility - async-safe wrapper.

        This uses the sync SQLAlchemy session (Flask-SQLAlchemy) but executes queries
        on worker threads via `asyncio.to_thread`, so your async endpoint is not
        blocked.
        """
        if not query_params:
            query_params = {}

        config = _QBConfig(
            allowed_filters=[
                "name",
                "category",
                "price",
                "discount",
                "user_id",
                "description",
                "stock",
                "ratings_average",
                "ratings_quantity",
                "slug",
                "created_at",
            ],
            allowed_sorts=[
                "name",
                "price",
                "ratings_average",
                "created_at",
            ],
            default_sort="-created_at",
            max_limit=50,
            search_fields=["name", "description"],
            enable_full_text_search=True,
            filter_map={
                "rating": "ratings_average",
                "popularity": "sold",
                "available": "stock",
            },
            param_aliases={
                "q": "search",
                "category_name": "category",
                "min_price": "price[gte]",
                "max_price": "price[lte]",
                "min_rating": "ratings_average[gte]",
            },
            date_format_fields={
                "created_at": "YYYY-MM-DD HH24:MI:SS",
                "updated_at": "YYYY-MM-DD HH24:MI:SS",
            },
        )

        qb = QueryBuilder(
            session=db.session,
            model=PublicProductsViewModel,
            query_params=query_params,
            config=config,
        )

        return await qb.execute()
