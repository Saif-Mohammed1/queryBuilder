from typing import Dict, List, Optional, Any, Union, Type
from sqlalchemy import or_, desc, asc, text, func
from sqlalchemy.orm import Query, Session
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio
from concurrent.futures import ThreadPoolExecutor
import re
import logging

from .queryBuilder_types import (
    QueryBuilderConfig, 
    QueryBuilderResult, 
    PaginationMeta, 
    JoinConfig, 
    JoinType, 
    Operator, 
    QueryBuilderError
)

logger = logging.getLogger(__name__)

class QueryBuilder:
    """
    Python equivalent of TypeScript QueryBuilder for SQLAlchemy
    
    Example usage:
        # Basic filtering and pagination
        qb = QueryBuilder(
            session=db.session,
            model=ProductModel,
            query_params={'category': 'electronics', 'page': '2', 'limit': '10'},
            config=QueryBuilderConfig(
                allowed_filters=['name', 'category', 'price', 'active'],
                allowed_sorts=['name', 'price', 'created_at'],
                max_limit=50
            )
        )
        
        # With joins
        result = await qb.join(JoinConfig(
            table='product_images',
            alias='pi',
            type=JoinType.LEFT,
            on_left='_id',
            on_right='product_id',
            select=['_id', 'link', 'public_id'],
            outer_key='images'
        )).execute()
    """
    
    def __init__(
        self,
        session: Union[Session, AsyncSession],
        model: Type,
        query_params: Dict[str, Any],
        config: QueryBuilderConfig,
        is_aggregate_enabled: bool = False
    ):
        self.session = session
        self.model = model
        self.table_name = model.__tablename__
        self.config = config
        self.is_aggregate_enabled = is_aggregate_enabled
        self.is_async_session = isinstance(session, AsyncSession)
        
        # Parse query parameters
        self.original_params = self._normalize_params(query_params)
        
        # Initialize query components
        self.query: Query = session.query(model)
        self.joins: List[JoinConfig] = []
        self.total_count: Optional[int] = None
        
        # Pagination defaults
        self.page: int = 1
        self.limit: int = config.max_limit
        self.filters: Dict[str, Any] = {}
        
        # Sanitize input parameters
        self._sanitize_input()

    def _normalize_params(self, params: Dict[str, Any]) -> Dict[str, str]:
        """Normalize query parameters to string values"""
        normalized = {}
        for key, value in params.items():
            if isinstance(value, list):
                # Handle multiple values (e.g., from URL query arrays)
                normalized[key] = ','.join(str(v) for v in value)
            else:
                normalized[key] = str(value) if value is not None else ''
        return normalized

    def _sanitize_input(self) -> None:
        """Remove invalid parameters"""
        valid_params = {}
        for key, value in self.original_params.items():
            if value and self._is_valid_param(key):
                valid_params[key] = value
        self.original_params = valid_params

    def _is_valid_param(self, key: str) -> bool:
        """Check if parameter is valid"""
        # Standard parameters
        if key in ['page', 'limit', 'sort', 'search', 'fields']:
            return True
        
        # Extract base key (remove operators like [gt], [in])
        base_key = re.sub(r'\[.*\]', '', key)
        
        # Check aliases
        aliased_key = self.config.param_aliases.get(base_key, base_key)
        
        # Check filter mapping
        db_field = self.config.filter_map.get(aliased_key, aliased_key)
        
        # Remove table prefix if present
        if isinstance(db_field, str) and '.' in db_field:
            if db_field.split('.')[0] == self.table_name:
                db_field = db_field.split('.')[1]
        
        return db_field in self.config.allowed_filters

    def _parse_value(self, value: str) -> Any:
        """Parse string value to appropriate type"""
        if ',' in value:
            return [self._parse_value(v.strip()) for v in value.split(',')]
        
        # Integer
        if re.match(r'^\d+$', value):
            return int(value)
        
        # Float
        if re.match(r'^\d+\.\d+$', value):
            return float(value)
        
        # Boolean
        if value.lower() == 'true':
            return True
        if value.lower() == 'false':
            return False
        
        return value

    def join(self, join_config: JoinConfig) -> 'QueryBuilder':
        """Add a join to the query"""
        self.joins.append(join_config)
        return self

    def _apply_joins(self) -> 'QueryBuilder':
        """Apply all configured joins"""
        for join_config in self.joins:
            alias = join_config.alias or join_config.table
            
            # Build join columns
            # left_column = getattr(self.model, join_config.on_left)
            
            # Get the joined table model (this would need to be passed or resolved)
            # For now, we'll use raw table names
            join_table = f"{join_config.table} AS {alias}"
            right_column = f"{alias}.{join_config.on_right}"
            
            if join_config.type == JoinType.INNER:
                self.query = self.query.join(
                    text(join_table), 
                    text(f"{self.table_name}.{join_config.on_left} = {right_column}")
                )
            elif join_config.type == JoinType.LEFT:
                self.query = self.query.outerjoin(
                    text(join_table), 
                    text(f"{self.table_name}.{join_config.on_left} = {right_column}")
                )
            # Add other join types as needed
        
        return self

    def _build_filter(self) -> 'QueryBuilder':
        """Build WHERE clauses from parameters"""
        where_clauses = {}
        
        for key, value in self.original_params.items():
            # Handle operator syntax (e.g., price[gt], status[in])
            operator_match = re.match(r'(\w+)\[(\w+)\]', key)
            if operator_match:
                base_key, operator = operator_match.groups()
            else:
                base_key, operator = key, None
            
            # Skip special parameters
            if base_key in ['page', 'limit', 'sort', 'fields', 'search']:
                continue
            
            # Handle search separately
            if base_key == 'search':
                self._handle_text_search(value)
                continue
            
            # Skip if this field is already handled by fixed_filters to avoid duplicates
            if base_key in self.config.fixed_filters:
                continue
            
            # Get aliased and mapped field
            aliased_key = self.config.param_aliases.get(base_key, base_key)
            db_field = self.config.filter_map.get(aliased_key, aliased_key)
            
            # Validate field
            field_name = db_field.split('.')[-1] if '.' in db_field else db_field
            if field_name not in self.config.allowed_filters:
                continue
            
            # Parse value
            parsed_value = self._parse_value(value)
            
            # Get model attribute
            if hasattr(self.model, field_name):
                column = getattr(self.model, field_name)
            else:
                continue
            
            # Apply operator
            if operator:
                self._apply_operator(column, operator, parsed_value)
            else:
                # Default equality
                where_clauses[field_name] = parsed_value
        
        # Apply simple where clauses
        if where_clauses:
            self.query = self.query.filter_by(**where_clauses)
        
        # Apply fixed filters
        if self.config.fixed_filters:
            for field, value in self.config.fixed_filters.items():
                if hasattr(self.model, field):
                    column = getattr(self.model, field)
                    self.query = self.query.filter(column == value)
        
        return self

    def _apply_operator(self, column, operator: str, value: Any) -> None:
        """Apply specific operators to column"""
        try:
            if operator == 'gt':
                self.query = self.query.filter(column > value)
            elif operator == 'gte':
                self.query = self.query.filter(column >= value)
            elif operator == 'lt':
                self.query = self.query.filter(column < value)
            elif operator == 'lte':
                self.query = self.query.filter(column <= value)
            elif operator == 'ne':
                self.query = self.query.filter(column != value)
            elif operator == 'in':
                if isinstance(value, list):
                    self.query = self.query.filter(column.in_(value))
                else:
                    logger.warning(f"IN operator requires list value, got: {type(value)}")
            elif operator == 'nin':
                if isinstance(value, list):
                    self.query = self.query.filter(~column.in_(value))
                else:
                    logger.warning(f"NOT IN operator requires list value, got: {type(value)}")
            elif operator == 'li':
                self.query = self.query.filter(column.like(f"%{value}%"))
            elif operator == 'ili':
                self.query = self.query.filter(column.ilike(f"%{value}%"))
            elif operator == 'con':
                # PostgreSQL JSONB contains operator
                self.query = self.query.filter(column.op('@>')(value))
            else:
                logger.warning(f"Unsupported operator: {operator}")
        except Exception as e:
            logger.error(f"Error applying operator {operator}: {str(e)}")

    def _handle_text_search(self, search_term: str) -> None:
        """Handle full-text search"""
        if not self.config.enable_full_text_search or not self.config.search_fields:
            return
        
        # Build search conditions
        search_conditions = []
        for field in self.config.search_fields:
            if hasattr(self.model, field):
                column = getattr(self.model, field)
                search_conditions.append(column.ilike(f"%{search_term}%"))
        
        if search_conditions:
            self.query = self.query.filter(or_(*search_conditions))

    def _build_sort(self) -> 'QueryBuilder':
        """Build ORDER BY clauses"""
        sort_param = self.original_params.get('sort', self.config.default_sort)
        sorts = [s.strip() for s in sort_param.split(',')]
        
        for sort_item in sorts:
            # Handle direction prefix
            if sort_item.startswith('-'):
                field, direction = sort_item[1:], 'desc'
            else:
                field, direction = sort_item, 'asc'
            
            # Handle explicit direction (field:desc)
            if ':' in field:
                field, direction = field.split(':', 1)
            
            # Map field name
            db_field = self.config.filter_map.get(field, field)
            
            # Validate sort field
            if db_field in self.config.allowed_sorts and hasattr(self.model, db_field):
                column = getattr(self.model, db_field)
                if direction.lower() == 'desc':
                    self.query = self.query.order_by(desc(column))
                else:
                    self.query = self.query.order_by(asc(column))
        
        return self

    def _build_pagination(self) -> 'QueryBuilder':
        """Build pagination parameters"""
        self.page = max(1, int(self.original_params.get('page', 1)))
        self.limit = min(
            self.config.max_limit,
            int(self.original_params.get('limit', self.config.max_limit))
        )
        return self

    def _build_projection(self) -> 'QueryBuilder':
        """Build SELECT clauses"""
        # Handle field selection
        if 'fields' in self.original_params:
            fields = [f.strip() for f in self.original_params['fields'].split(',')]
            select_fields = []
            
            for field in fields:
                mapped_field = self.config.filter_map.get(field, field)
                if mapped_field in self.config.allowed_filters and hasattr(self.model, mapped_field):
                    # Handle date formatting
                    if field in self.config.date_format_fields:
                        date_format = self.config.date_format_fields[field]
                        column = getattr(self.model, mapped_field)
                        formatted_column = func.to_char(column, date_format).label(field)
                        select_fields.append(formatted_column)
                    else:
                        select_fields.append(getattr(self.model, mapped_field))
            
            if select_fields:
                self.query = self.query.with_entities(*select_fields)
        
        elif self.config.select_fields:
            # Use configured select fields
            select_fields = []
            for field in self.config.select_fields:
                if hasattr(self.model, field):
                    # Handle date formatting
                    if field in self.config.date_format_fields:
                        date_format = self.config.date_format_fields[field]
                        column = getattr(self.model, field)
                        formatted_column = func.to_char(column, date_format).label(field)
                        select_fields.append(formatted_column)
                    else:
                        select_fields.append(getattr(self.model, field))
            
            if select_fields:
                self.query = self.query.with_entities(*select_fields)
        
        return self

    async def _get_total_count(self) -> int:
        """Get total count for pagination"""
        if self.total_count is not None:
            return self.total_count
        
        # Create a count query without pagination and ordering
        count_query = self.query.order_by(None).statement.with_only_columns(func.count())
        
        try:
            result = self.session.execute(count_query).scalar()
            self.total_count = result or 0
        except Exception as e:
            logger.error(f"Error getting total count: {str(e)}")
            self.total_count = 0
        
        return self.total_count

    def aggregate(self, queries: List[str], group_by: List[str]) -> 'QueryBuilder':
        """Add aggregation to query"""
        # This would need more sophisticated implementation for complex aggregations
        raw_selects = [text(query) for query in queries]
        self.query = self.query.with_entities(*raw_selects)
        
        if group_by:
            group_columns = []
            for field in group_by:
                if hasattr(self.model, field):
                    group_columns.append(getattr(self.model, field))
            if group_columns:
                self.query = self.query.group_by(*group_columns)
        
        return self

    async def execute(self) -> QueryBuilderResult:
        """Execute the query and return results"""
        try:
            # Build the complete query
            self._apply_joins()
            self._build_filter()
            self._build_sort()
            self._build_pagination()
            self._build_projection()
            
            # Handle joins with aggregation
            if not self.is_aggregate_enabled and self.joins:
                # This would need more sophisticated handling for joins
                # For now, we'll just execute the basic query
                pass
            
            # Use ThreadPoolExecutor for regular Flask-SQLAlchemy sessions
            if not self.is_async_session:
                # Capture Flask context
                from flask import current_app
                app = current_app._get_current_object()
                
                def _execute_with_context(func_name):
                    with app.app_context():
                        if func_name == 'data':
                            return self._execute_data_query_sync()
                        else:
                            return self._execute_count_query_sync()

                loop = asyncio.get_running_loop()
                with ThreadPoolExecutor() as executor:
                    # Execute data query and count query concurrently
                    data_future = loop.run_in_executor(
                        executor, 
                        lambda: _execute_with_context('data')
                    )
                    count_future = loop.run_in_executor(
                        executor, 
                        lambda: _execute_with_context('count')
                    )
                    
                    # Wait for both to complete
                    data, total = await asyncio.gather(data_future, count_future)
            else:
                # For true AsyncSession (if ever implemented)
                # data = await self._execute_data_query_async()
                # total = await self._execute_count_query_async()
              data, total = await asyncio.gather(
                    self._execute_data_query_async(),
                    self._execute_count_query_async()
                )
            
            # Calculate pagination metadata
            total_pages = (total + self.limit - 1) // self.limit
            meta = PaginationMeta(
                total=total,
                page=self.page,
                limit=self.limit,
                total_pages=total_pages,
                has_next=self.page < total_pages,
                has_prev=self.page > 1
            )
            
            return QueryBuilderResult(
                docs=data,
                meta=meta,
                links=self._build_links(total_pages)
            )
            
        except Exception as error:
            logger.error(f"QueryBuilder Error: {str(error)}")
            raise QueryBuilderError("Failed to execute query", error)

    def _build_links(self, total_pages: int) -> Dict[str, str]:
        """Build pagination links"""
        links = {}
        params = dict(self.original_params)
        
        # Remove excluded fields
        for field in self.config.exclude_links_fields:
            params.pop(field, None)
        
        # Build different page links
        link_configs = {
            'first': 1,
            'prev': self.page - 1,
            'next': self.page + 1,
            'last': total_pages
        }
        
        for rel, page_num in link_configs.items():
            if ((rel == 'prev' and self.page > 1) or 
                (rel == 'next' and self.page < total_pages) or 
                rel in ['first', 'last']):
                
                params['page'] = str(page_num)
                query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
                links[rel] = f"?{query_string}"
        
        return links

    def _execute_data_query_sync(self) -> List[Any]:
        """Execute data query synchronously"""
        paginated_query = self.query.offset((self.page - 1) * self.limit).limit(self.limit)
        return paginated_query.all()
    
    def _execute_count_query_sync(self) -> int:
        """Execute count query synchronously"""
        count_query = self.query.order_by(None).statement.with_only_columns(func.count())
        return self.session.execute(count_query).scalar() or 0
    
    async def _execute_data_query_async(self) -> List[Any]:
        """Execute data query asynchronously (for AsyncSession)"""
        # This would be implemented if using AsyncSession
        raise NotImplementedError("AsyncSession not yet implemented")
    
    async def _execute_count_query_async(self) -> int:
        """Execute count query asynchronously (for AsyncSession)"""
        # This would be implemented if using AsyncSession
        raise NotImplementedError("AsyncSession not yet implemented")
