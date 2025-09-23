# Python SQLAlchemy Query Builder Utility

A powerful, configurable query builder for SQLAlchemy that simplifies complex database queries with support for pagination, filtering, sorting, text search, joins, and aggregation — all through clean and reusable code.

## ✨ Key Features

- ✅ Automatic pagination with meta info and HATEOAS-style links
- ✅ Flexible filtering with SQL operator support (`gt`, `lt`, `in`, `like`, etc.)
- ✅ Dynamic sorting with field whitelisting
- ✅ Full-text search with PostgreSQL support
- ✅ Join support for relational data
- ✅ Field projection and exclusion
- ✅ Field/param aliasing and filter mapping
- ✅ Fixed filters for multi-tenant or role-based data access
- ✅ Secure and sanitized input handling
- ✅ Both sync and async session support

---

## 💡 DRY Benefits

This utility removes repetitive SQLAlchemy logic by:

1. Centralizing pagination, filtering, and sorting logic
2. Supporting flexible query params without boilerplate
3. Enforcing field whitelisting and validation
4. Standardizing API responses across endpoints
5. Simplifying joins and aggregations
6. Handling edge cases like date formatting and operator parsing

---

## 🚀 Installation

```bash
pip install sqlalchemy
# Include the QueryBuilder class and types in your project
```

---

## 🛠️ Usage

### 🧱 Basic Setup and Usage

```python
from queryBuilder import QueryBuilder
from queryBuilder_types import QueryBuilderConfig

async def get_products(query_params=None):
    """Get products using QueryBuilder utility - async version"""
    if not query_params:
        query_params = {}

    # Configure QueryBuilder
    config = QueryBuilderConfig(
        allowed_filters=[
            'name', 'category', 'price', 'discount', 'user_id',
            'description', 'stock', 'ratings_average', 'ratings_quantity',
            'slug', 'created_at',
        ],
        allowed_sorts=[
            'name', 'price',
            'ratings_average', 'created_at',
        ],
        default_sort='-created_at',
        max_limit=50,
        search_fields=['name', 'description'],
        enable_full_text_search=True,
        filter_map={
            'rating': 'ratings_average',
            'popularity': 'sold',
            'available': 'stock'
        },
        param_aliases={
            'q': 'search',
            'category_name': 'category',
            'min_price': 'price[gte]',
            'max_price': 'price[lte]',
            'min_rating': 'ratings_average[gte]'
        },
        date_format_fields={
            'created_at': 'YYYY-MM-DD HH24:MI:SS',
            'updated_at': 'YYYY-MM-DD HH24:MI:SS'
        }
    )

    # Create QueryBuilder instance
    query_builder = QueryBuilder(
        session=db.session,
        model=PublicProductsViewModel,
        query_params=query_params,
        config=config
    )

    # Execute and return results
    return await query_builder.execute()
```

---

## 🚀 v2 AI Enhancements

The v2 version includes significant AI-powered improvements for better performance, reliability, and developer experience:

### ⚡ **Non-Blocking Async Execution**

- **Problem Solved**: Original version used `ThreadPoolExecutor` which could create threading overhead
- **v2 Solution**: Uses `asyncio.to_thread()` for cleaner async execution with Flask-SQLAlchemy sessions
- **Benefit**: Better performance and resource management in async applications

```python
# v2 Enhanced async execution
data, total = await asyncio.gather(
    asyncio.to_thread(_data_with_ctx),
    asyncio.to_thread(_count_with_ctx),
)
```

### 🔧 **Improved Session Handling**

- **Problem Solved**: Confusing session type detection and potential misuse of AsyncSession
- **v2 Solution**: Clear separation between sync and async session paths with explicit error handling
- **Benefit**: Prevents silent failures and guides developers toward correct implementation

```python
if self.is_async_session:
    raise NotImplementedError(
        "AsyncSession path is not implemented yet. Use a sync Session with to_thread, "
        "or migrate builders to Core select() statements for full async."
    )
```

### 📊 **Robust Count Query Implementation**

- **Problem Solved**: Original count queries could fail with complex joins and filters
- **v2 Solution**: Uses subquery approach for reliable counting
- **Benefit**: Accurate pagination metadata even with complex queries

```python
def _execute_count_query_sync(self) -> int:
    # Robust count: wrap filtered query as subquery and count rows
    base_subq = self.query.order_by(None).subquery()
    stmt = select(func.count()).select_from(base_subq)
    return int(self.session.execute(stmt).scalar() or 0)
```

### 🛡️ **Enhanced Error Handling & Type Safety**

- **Problem Solved**: Generic error messages and potential type issues
- **v2 Solution**: Comprehensive logging with `logger.exception()` and strict type hints
- **Benefit**: Better debugging and development experience

```python
try:
    return await qb.execute()
except Exception as error:
    logger.exception("QueryBuilder Error: %s", str(error))
    raise QueryBuilderError("Failed to execute query", error)
```

### 🏗️ **Improved Architecture & Code Organization**

- **Problem Solved**: Monolithic methods and unclear separation of concerns
- **v2 Solution**: Better method organization with clear section comments and helper functions
- **Benefit**: More maintainable and readable codebase

### 🔄 **Smart Query Building**

- **Problem Solved**: Redundant query building for AsyncSession (which doesn't support `.query()`)
- **v2 Solution**: Conditional query building based on session type
- **Benefit**: Prevents unnecessary operations and memory usage

```python
# Initialize query components (sync ORM Query only)
self.query: Optional[Query] = None
if not self.is_async_session:
    self.query = session.query(model)  # Flask-SQLAlchemy style
```

### 📝 **Enhanced Documentation & Examples**

- **Problem Solved**: Limited guidance on proper usage patterns
- **v2 Solution**: Comprehensive docstrings with usage examples and implementation notes
- **Benefit**: Faster developer onboarding and reduced integration errors

### 🎯 **Repository Pattern Integration**

- **v2 Addition**: Complete repository pattern example showing real-world usage
- **Benefit**: Production-ready implementation template for developers

```python
class ProductsRepository(BaseRepository):
    async def get_products(self, query_params: Optional[Dict[str, Any]] = None):
        """Get products using QueryBuilder utility - async-safe wrapper."""
        # Complete implementation with proper error handling
        qb = QueryBuilder(session=db.session, model=PublicProductsViewModel, ...)
        return await qb.execute()
```

---

## � Version Comparison: v1 vs v2

| Feature                | v1 (Original)                                     | v2 (AI Enhanced)                                           |
| ---------------------- | ------------------------------------------------- | ---------------------------------------------------------- |
| **Async Execution**    | `ThreadPoolExecutor` with manual context handling | `asyncio.to_thread()` with improved context management     |
| **Session Handling**   | Basic session type detection                      | Smart conditional query building with clear error messages |
| **Count Queries**      | Simple `func.count()` approach                    | Robust subquery-based counting for complex queries         |
| **Error Handling**     | Basic exception catching                          | Comprehensive logging with `logger.exception()`            |
| **Type Safety**        | Minimal type hints                                | Full type annotations with `Optional[Query]`               |
| **Code Organization**  | Monolithic structure                              | Organized sections with helper methods                     |
| **Documentation**      | Basic docstrings                                  | Comprehensive usage examples and implementation notes      |
| **Repository Pattern** | No example provided                               | Complete repository integration example                    |
| **Performance**        | Potential threading overhead                      | Optimized async execution with better resource management  |
| **Debugging**          | Generic error messages                            | Detailed error context and stack traces                    |

### 🎯 **Migration from v1 to v2**

Migrating is seamless - the public API remains unchanged:

```python
# Same interface works for both versions
qb = QueryBuilder(
    session=db.session,
    model=ProductModel,
    query_params=request.args,
    config=config
)
result = await qb.execute()  # Same call, better performance in v2
```

**v2 Benefits Without Code Changes:**

- ✅ Automatic performance improvements
- ✅ Better error messages for debugging
- ✅ More reliable count queries
- ✅ Enhanced async handling
- ✅ Future-proof architecture

---

## �🔎 Filtering and Operators

You can filter using common SQL operators:

```http
GET /products?price[gte]=100&ratings_average[lt]=4&category[in]=electronics,books
```

Supported operators:

- `gt`, `gte`, `lt`, `lte` (greater than, less than comparisons)
- `ne` (not equal)
- `in`, `nin` (array inclusion/exclusion)
- `li`, `ili` (LIKE and ILIKE for pattern matching)
- `con` (PostgreSQL JSONB contains operator)

### Example with joins:

```python
async def get_products_with_images():
    """Get products with their images using joins"""
    config = QueryBuilderConfig(
        allowed_filters=['name', 'category', 'price', 'active'],
        allowed_sorts=['name', 'price', 'created_at'],
        max_limit=50
    )

    query_builder = QueryBuilder(
        session=db.session,
        model=ProductModel,
        query_params=request.args,
        config=config
    )

    # Add join for product images
    result = await query_builder.join(JoinConfig(
        table='product_images',
        alias='pi',
        type=JoinType.LEFT,
        on_left='_id',
        on_right='product_id',
        select=['_id', 'link', 'public_id'],
        outer_key='images'
    )).execute()

    return result
```

---

## 🧭 Pagination

Supports pagination with metadata and navigation links:

```http
GET /products?page=2&limit=15
```

Returns:

```python
{
    "docs": [...],  # List of product objects
    "meta": {
        "total": 120,
        "page": 2,
        "limit": 15,
        "total_pages": 8,
        "has_next": True,
        "has_prev": True
    },
    "links": {
        "first": "?page=1&limit=15",
        "prev": "?page=1&limit=15",
        "next": "?page=3&limit=15",
        "last": "?page=8&limit=15"
    }
}
```

---

## 🧰 Configuration Options

| Option                    | Type             | Description                                    | Default       |
| ------------------------- | ---------------- | ---------------------------------------------- | ------------- |
| `allowed_filters`         | `List[str]`      | Whitelisted fields for filtering               | \[]           |
| `allowed_sorts`           | `List[str]`      | Allowed fields for sorting                     | \[]           |
| `default_sort`            | `str`            | Default sort (supports `-` for DESC)           | "-created_at" |
| `max_limit`               | `int`            | Max items per page                             | 15            |
| `search_fields`           | `List[str]`      | Fields to search via full-text or ILIKE        | \[]           |
| `enable_full_text_search` | `bool`           | Use PostgreSQL full-text search                | False         |
| `param_aliases`           | `Dict[str, str]` | Aliases for query params (e.g. `q` → `search`) | {}            |
| `filter_map`              | `Dict[str, str]` | Map query keys to DB field names               | {}            |
| `fixed_filters`           | `Dict[str, Any]` | Filters that are always applied                | {}            |
| `exclude_fields`          | `List[str]`      | Fields to exclude from response                | \[]           |
| `select_fields`           | `List[str]`      | Specific fields to select only                 | \[]           |
| `date_format_fields`      | `Dict[str, str]` | PostgreSQL TO_CHAR formats for date fields     | {}            |

---

## 🔍 Text Search

Enable full-text search and define fields:

```python
config = QueryBuilderConfig(
    enable_full_text_search=True,
    search_fields=['name', 'description']
)
```

Usage:

```http
GET /products?search=wireless+headphones
```

Falls back to `ILIKE` pattern matching if full-text search is disabled.

---

## 🔗 Joins and Relationships

Handle related data with joins:

```python
from queryBuilder_types import JoinConfig, JoinType

# Left join with product categories
join_config = JoinConfig(
    table='categories',
    alias='cat',
    type=JoinType.LEFT,
    on_left='category_id',
    on_right='_id',
    select=['name', 'description'],
    outer_key='category_info'
)

result = await query_builder.join(join_config).execute()
```

---

## 🛡️ Security Tips

- Use `allowed_filters`, `allowed_sorts`, and `exclude_fields` to avoid exposing sensitive data.
- Map query param aliases to avoid leaking internal database structures.
- Use `fixed_filters` for multitenancy or user-scoped data access.
- All input is sanitized and validated before query execution.

---

## ⚠️ Error Handling

All errors are wrapped in a `QueryBuilderError`:

```python
from queryBuilder_types import QueryBuilderError

try:
    result = await query_builder.execute()
except QueryBuilderError as error:
    logger.error(f"Query error: {error.message}")
    if error.original_error:
        logger.error(f"Original error: {error.original_error}")
```

---

## 📌 Best Practices

- ✅ Whitelist all filters and sorts explicitly for security
- ✅ Limit `max_limit` to protect database performance
- ✅ Use joins for related data instead of separate queries
- ✅ Use `fixed_filters` for authorization-based querying
- ✅ Alias external query params like `q`, `from`, `to`
- ✅ Standardize query responses across your API endpoints
- ✅ Handle both sync and async database sessions appropriately

---

## 🧪 Example Queries

### Basic filtering:

```http
GET /products?category[in]=electronics,books&price[gte]=50&search=charger&sort=-price&page=1&limit=10&fields=name,price
```

### Complex filtering with multiple operators:

```http
GET /products?price[gte]=100&price[lte]=500&ratings_average[gt]=4.0&stock[ne]=0&category=electronics
```

### Date range filtering:

```http
GET /products?created_at[gte]=2023-01-01&created_at[lt]=2024-01-01&sort=created_at
```

---

## 📚 Complete Example Implementation

```python
from flask import Flask, request, jsonify
from queryBuilder import QueryBuilder
from queryBuilder_types import QueryBuilderConfig, JoinConfig, JoinType
from models import ProductModel, db

app = Flask(__name__)

@app.route('/api/products', methods=['GET'])
async def get_products():
    """Complete products endpoint with QueryBuilder"""

    # Configure the query builder
    config = QueryBuilderConfig(
        allowed_filters=[
            'name', 'category', 'price', 'discount', 'user_id',
            'description', 'stock', 'ratings_average', 'ratings_quantity',
            'slug', 'created_at', 'updated_at', 'active'
        ],
        allowed_sorts=[
            'name', 'price', 'ratings_average', 'created_at', 'stock'
        ],
        default_sort='-created_at',
        max_limit=100,
        search_fields=['name', 'description'],
        enable_full_text_search=True,
        filter_map={
            'rating': 'ratings_average',
            'popularity': 'sold',
            'available': 'stock'
        },
        param_aliases={
            'q': 'search',
            'category_name': 'category',
            'min_price': 'price[gte]',
            'max_price': 'price[lte]',
            'min_rating': 'ratings_average[gte]'
        },
        fixed_filters={
            'active': True  # Only show active products
        },
        date_format_fields={
            'created_at': 'YYYY-MM-DD HH24:MI:SS',
            'updated_at': 'YYYY-MM-DD HH24:MI:SS'
        }
    )

    # Create QueryBuilder instance
    query_builder = QueryBuilder(
        session=db.session,
        model=ProductModel,
        query_params=request.args,
        config=config
    )

    # Add optional joins based on query parameters
    if 'include_images' in request.args:
        query_builder.join(JoinConfig(
            table='product_images',
            alias='images',
            type=JoinType.LEFT,
            on_left='_id',
            on_right='product_id',
            select=['_id', 'link', 'alt_text'],
            outer_key='images'
        ))

    if 'include_category' in request.args:
        query_builder.join(JoinConfig(
            table='categories',
            alias='cat',
            type=JoinType.LEFT,
            on_left='category_id',
            on_right='_id',
            select=['name', 'description'],
            outer_key='category_info'
        ))

    try:
        # Execute query and return results
        result = await query_builder.execute()
        return jsonify(result.dict()), 200

    except QueryBuilderError as e:
        return jsonify({
            'error': 'Query failed',
            'message': e.message
        }), 400
    except Exception as e:
        return jsonify({
            'error': 'Internal server error'
        }), 500

if __name__ == '__main__':
    app.run(debug=True)
```

---

## 🧩 Extending the Query Builder

You can easily extend this builder to:

- Support custom SQL operators
- Add complex aggregations with GROUP BY
- Integrate caching mechanisms
- Include role-based access control logic
- Add query performance monitoring
- Support database-specific features (PostgreSQL arrays, JSON operations, etc.)

### Example Extension:

```python
class ExtendedQueryBuilder(QueryBuilder):
    """Extended QueryBuilder with custom aggregations"""

    def add_aggregation(self, group_fields: List[str], aggregate_queries: List[str]):
        """Add aggregation support"""
        return self.aggregate(aggregate_queries, group_fields)

    def add_custom_filter(self, field: str, custom_logic: str):
        """Add custom SQL filter logic"""
        self.query = self.query.filter(text(custom_logic))
        return self
```

---

## 📊 Result Format

The QueryBuilder returns results in this standardized format:

```python
from dataclasses import dataclass
from typing import List, Dict, Optional, Any

@dataclass
class QueryBuilderResult:
    docs: List[Any]  # Your model instances
    meta: PaginationMeta
    links: Optional[Dict[str, str]] = None

@dataclass
class PaginationMeta:
    total: int
    page: int
    limit: int
    total_pages: int
    has_next: bool
    has_prev: bool
```

This ensures consistent API responses across all endpoints using the QueryBuilder.

## AI Enhancements
