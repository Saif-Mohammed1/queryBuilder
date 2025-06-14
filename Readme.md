````markdown
# Knex Query Builder Utility

A powerful, configurable query builder for Knex.js that simplifies complex data fetching with pagination, filtering, sorting, and joins while enforcing DRY principles.

## Key Features

- **Automatic pagination** with metadata and HATEOAS links
- **Flexible filtering** with operator support (`gt`, `lt`, `in`, etc.)
- **Dynamic sorting** with field whitelisting
- **Join handling** with automatic JSON aggregation
- **Field selection** and projection control
- **Full-text search** integration
- **Aggregation support** for complex queries
- **Date formatting** for specific fields
- **Security** through input sanitization and allowed field checks

## DRY Benefits

This utility eliminates repetitive query patterns by:

1. Centralizing common data fetching logic
2. Abstracting complex SQL operations (joins, aggregation)
3. Standardizing response formats (pagination metadata, links)
4. Reducing boilerplate for filtering/sorting
5. Providing configuration-driven behavior
6. Handling edge cases consistently across endpoints

## Installation

```bash
npm install knex
# No separate installation needed - include the class file
```
````

## Usage

### Basic Setup

```typescript
import { QueryBuilder } from "./queryBuilder";
import type { QueryBuilderConfig } from "./queryBuilder.types";

const config: QueryBuilderConfig<Product> = {
  allowedFilters: ["name", "price", "category"],
  allowedSorts: ["created_at", "price"],
  maxLimit: 50,
  searchFields: ["name", "description"],
  defaultSort: "-created_at",
  selectFields: ["id", "name", "price"],
  dateFormatFields: {
    created_at: "YYYY-MM-DD HH24:MI",
  },
};

const queryParams = new URLSearchParams(req.query);
const builder = new QueryBuilder(knex, "products", queryParams, config);
```

### Join Handling

```typescript
builder
  .join({
    table: "product_images",
    alias: "pi",
    type: "left",
    on: { left: "_id", right: "product_id" },
    select: ["url", "alt_text"],
    outerKey: "images", // Optional custom key
  })
  .join({
    table: "inventory",
    alias: "inv",
    type: "inner",
    on: { left: "sku", right: "product_sku" },
    select: ["quantity"],
  });
```

### Aggregation

```typescript
builder.aggregate(
  [
    `JSON_AGG(DISTINCT categories.name) AS categories`,
    `SUM(inv.quantity) AS total_stock`,
  ],
  ["products.id"]
);
```

### Execution

```typescript
const result = await builder.execute();

// Returns:
{
  docs: [
    {
      id: 123,
      name: 'Example',
      images: [
        { url: 'img1.jpg', alt_text: 'Main' },
        { url: 'img2.jpg', alt_text: 'Back' }
      ],
      total_stock: 42
    }
  ],
  meta: {
    total: 100,
    page: 1,
    limit: 15,
    totalPages: 7,
    hasNext: true,
    hasPrev: false
  },
  links: {
    first: '?page=1&limit=15',
    next: '?page=2&limit=15',
    last: '?page=7&limit=15'
  }
}
```

## Configuration Options

| Option                 | Type                               | Description                  | Default       |
| ---------------------- | ---------------------------------- | ---------------------------- | ------------- |
| `maxLimit`             | number                             | Max items per page           | 15            |
| `enableFullTextSearch` | boolean                            | Enable full-text search      | false         |
| `allowedFilters`       | (keyof T)[]                        | Whitelisted filter fields    | []            |
| `allowedSorts`         | (keyof T)[]                        | Allowed sort fields          | []            |
| `defaultSort`          | string                             | Default sort field           | "-created_at" |
| `searchFields`         | string[]                           | Fields for text search       | []            |
| `selectFields`         | string[]                           | Default selected fields      | []            |
| `dateFormatFields`     | Record<string, string>             | Date formatting rules        | {}            |
| `paramAliases`         | Record<string, string>             | Query param aliases          | {}            |
| `filterMap`            | Record<string, string \| Knex.Raw> | Field name mappings          | {}            |
| `fixedFilters`         | Partial<T>                         | Always-applied filters       | {}            |
| `excludeLinksFields`   | string[]                           | Fields to exclude from links | []            |
| `totalCountBy`         | string[]                           | Fields for count queries     | []            |

## Advanced Features

### Custom Operators

Filter using operators in query params:

```http
GET /products?price[gt]=100&category[in]=electronics,home
```

Supported operators:

- `gt`, `gte`, `lt`, `lte`
- `ne` (not equal)
- `in`, `nin` (not in)
- `li` (LIKE), `ili` (ILIKE)
- `con` (contains - for arrays/JSON)

### Date Formatting

```typescript
dateFormatFields: {
  created_at: 'YYYY-MM-DD',
  updated_at: 'MM/DD/YYYY HH24:MI'
}
```

### Full-Text Search

Enable with:

```typescript
enableFullTextSearch: true,
searchFields: ['title', 'description', 'tags']
```

Then search with:

```http
GET /products?search=wireless+charging
```

### Custom Count Queries

```typescript
// For complex grouped queries
totalCountBy: ["category", "brand"];
```

### Link Generation

Automatic HATEOAS links with field exclusion:

```typescript
excludeLinksFields: ["api_key", "sensitive_param"];
```

## Error Handling

Catches errors and throws `QueryBuilderError` with original exception:

```typescript
try {
  await builder.execute();
} catch (err) {
  if (err instanceof QueryBuilderError) {
    console.error("DB Error:", err.originalError);
  }
}
```

## Best Practices

1. Always whitelist filter/sort fields
2. Use `fixedFilters` for tenant isolation (`user_id`)
3. Limit maximum items per page
4. Use field mappings for legacy systems
5. Prefer JSON aggregation for nested relations
6. Format dates at database level for consistency
7. Exclude sensitive params from pagination links

## Limitations

- PostgreSQL-specific features (JSON/Array functions)
- Complex joins might require custom aggregation
- Full-text search requires PostgreSQL configuration

```

```
