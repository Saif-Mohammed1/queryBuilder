from typing import Dict, List, Optional, Any, TypeVar, Generic
from dataclasses import dataclass
from enum import Enum

# Type variable for generic model
T = TypeVar('T')

class JoinType(Enum):
    INNER = "inner"
    LEFT = "left"
    RIGHT = "right"
    FULL = "full"

class Operator(Enum):
    EQ = "eq"      # =
    NE = "ne"      # <>
    GT = "gt"      # >
    GTE = "gte"    # >=
    LT = "lt"      # <
    LTE = "lte"    # <=
    IN = "in"      # IN
    NIN = "nin"    # NOT IN
    LIKE = "li"    # LIKE
    ILIKE = "ili"  # ILIKE
    CONTAINS = "con"  # @> (JSONB contains)

@dataclass
class JoinConfig:
    """Configuration for table joins"""
    table: str
    alias: Optional[str] = None
    type: JoinType = JoinType.LEFT
    on_left: str = ""  # Column in primary table (e.g., "_id")
    on_right: str = ""  # Column in joined table (e.g., "product_id")
    select: List[str] = None  # Fields to select from joined table
    outer_key: Optional[str] = None  # Key for aggregated data

    def __post_init__(self):
        if self.alias is None:
            self.alias = self.table
        if self.select is None:
            self.select = []

@dataclass
class PaginationMeta:
    """Pagination metadata"""
    total: int
    page: int
    limit: int
    total_pages: int
    has_next: bool
    has_prev: bool

@dataclass
class QueryBuilderResult(Generic[T]):
    """Result container for query builder"""
    docs: List[T]
    meta: PaginationMeta
    links: Optional[Dict[str, str]] = None

@dataclass
class QueryBuilderConfig:
    """Configuration for QueryBuilder"""
    # Fields allowed for filtering (WHERE clauses)
    allowed_filters: List[str]
    
    # Fields allowed for sorting (ORDER BY)
    allowed_sorts: Optional[List[str]] = None
    
    # Default sorting field and direction (e.g., '-created_at')
    default_sort: str = "-created_at"
    
    # Fields to use for full-text search
    search_fields: Optional[List[str]] = None
    
    # Maximum number of items per page
    max_limit: int = 15
    
    # Map query parameters to database columns
    filter_map: Optional[Dict[str, str]] = None
    
    # Alternate parameter names
    param_aliases: Optional[Dict[str, str]] = None
    
    # Enable PostgreSQL full-text search
    enable_full_text_search: bool = False
    
    # Fixed filters to apply to all queries
    fixed_filters: Optional[Dict[str, Any]] = None
    
    # Fields to exclude from results
    exclude_fields: Optional[List[str]] = None
    
    # Select specific fields only
    select_fields: Optional[List[str]] = None
    
    # Fields to count by for total count
    total_count_by: Optional[List[str]] = None
    
    # Fields to exclude from links
    exclude_links_fields: Optional[List[str]] = None
    
    # Date format fields (PostgreSQL TO_CHAR format)
    date_format_fields: Optional[Dict[str, str]] = None
    
    # Custom operators map
    operators: Optional[Dict[Operator, str]] = None

    def __post_init__(self):
        # Set defaults for optional fields
        if self.allowed_sorts is None:
            self.allowed_sorts = []
        if self.search_fields is None:
            self.search_fields = []
        if self.filter_map is None:
            self.filter_map = {}
        if self.param_aliases is None:
            self.param_aliases = {}
        if self.fixed_filters is None:
            self.fixed_filters = {}
        if self.exclude_fields is None:
            self.exclude_fields = []
        if self.select_fields is None:
            self.select_fields = []
        if self.total_count_by is None:
            self.total_count_by = []
        if self.exclude_links_fields is None:
            self.exclude_links_fields = []
        if self.date_format_fields is None:
            self.date_format_fields = {}
        if self.operators is None:
            self.operators = {}

class QueryBuilderError(Exception):
    """Custom exception for QueryBuilder errors"""
    def __init__(self, message: str, original_error: Exception = None):
        self.message = message
        self.original_error = original_error
        super().__init__(self.message)