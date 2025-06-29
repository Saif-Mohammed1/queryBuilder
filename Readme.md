Here’s a version of the `README.md` tailored to your **Mongoose QueryBuilder**, styled like the **Knex version** but fully compatible with MongoDB and Mongoose practices:

````markdown
# Mongoose Query Builder Utility

A powerful, configurable query builder for Mongoose that simplifies complex MongoDB queries with support for pagination, filtering, sorting, text search, projection, and population — all through clean and reusable code.

## ✨ Key Features

- ✅ Automatic pagination with meta info and HATEOAS-style links
- ✅ Flexible filtering with MongoDB operator support (`gt`, `lt`, `in`, etc.)
- ✅ Dynamic sorting with field whitelisting
- ✅ Text search (`$text` or regex fallback)
- ✅ Population support for relational fields
- ✅ Field projection and exclusion
- ✅ Field/param aliasing and filter mapping
- ✅ Fixed filters for multi-tenant or role-based data access
- ✅ Secure and sanitized input handling

---

## 💡 DRY Benefits

This utility removes repetitive Mongoose logic by:

1. Centralizing pagination, filtering, and sorting logic
2. Supporting flexible query params without boilerplate
3. Enforcing field whitelisting and validation
4. Standardizing API responses across endpoints
5. Simplifying `populate()` and projection
6. Handling edge cases like date parsing and operator merging

---

## 🚀 Installation

```bash
# No separate package needed
# Just include the QueryBuilder.ts class and types in your project
```
````

---

## 🛠️ Usage

### 🧱 Setup

```ts
import { QueryBuilder } from "./utils/queryBuilder";
import type { QueryBuilderConfig } from "./types/queryBuilder.types";

const config: QueryBuilderConfig<Product> = {
  allowedFilters: ["name", "price", "category"],
  allowedSorts: ["createdAt", "price"],
  defaultSort: "-createdAt",
  searchFields: ["name", "description"],
  maxLimit: 50,
  filterMap: {
    category: "categoryId",
  },
  paramAliases: {
    q: "search",
  },
  enableTextSearch: true,
};

const queryParams = new URLSearchParams(req.query);
const builder = new QueryBuilder(ProductModel, queryParams, config);
const result = await builder.execute();
```

---

## 🔎 Filtering and Operators

You can filter using common MongoDB operators:

```http
GET /products?price[gte]=100&rating[lt]=4&category[in]=electronics,books
```

Supported operators:

- `gt`, `gte`, `lt`, `lte`
- `ne` (not equal)
- `in`, `nin` (array inclusion)
- `regex` (pattern matching)

---

## 📦 Population

Populate referenced fields using:

```ts
builder.populate([
  { path: "user", select: "name email" },
  { path: "category", select: "title" },
]);
```

---

## 🧭 Pagination

Supports pagination with metadata and navigation links:

```http
GET /products?page=2&limit=15
```

Returns:

```json
{
  "docs": [...],
  "meta": {
    "total": 120,
    "page": 2,
    "limit": 15,
    "totalPages": 8,
    "hasNext": true,
    "hasPrev": true
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

| Option             | Type                      | Description                                    | Default      |
| ------------------ | ------------------------- | ---------------------------------------------- | ------------ |
| `allowedFilters`   | `(keyof T)[]`             | Whitelisted query fields for filtering         | \[]          |
| `allowedSorts`     | `(keyof T)[]`             | Allowed fields for sorting                     | \[]          |
| `defaultSort`      | `string`                  | Default sort (supports `-` for DESC)           | "-createdAt" |
| `maxLimit`         | `number`                  | Max items per page                             | 15           |
| `searchFields`     | `(keyof T)[]`             | Fields to search via `regex` or `$text`        | \[]          |
| `enableTextSearch` | `boolean`                 | Use MongoDB `$text` instead of regex           | false        |
| `paramAliases`     | `Record<string, string>`  | Aliases for query params (e.g. `q` → `search`) | {}           |
| `filterMap`        | `Record<string, keyof T>` | Map query keys to DB field names               | {}           |
| `fixedFilters`     | `FilterQuery<T>`          | Filters that are always applied                | {}           |
| `excludeFields`    | `(keyof T)[]`             | Fields to exclude from response                | \[]          |

---

## 🔍 Text Search

Enable text search and define fields:

```ts
enableTextSearch: true,
searchFields: ["title", "description"]
```

Usage:

```http
GET /products?search=wireless+headphones
```

Fallbacks to `regex` if `$text` is not enabled.

---

## 🛡️ Security Tips

- Use `allowedFilters`, `allowedSorts`, and `excludeFields` to avoid exposing sensitive data.
- Map query param aliases to avoid leaking internal database structures.
- Use `fixedFilters` for multitenancy or user-scoped data access.

---

## ⚠️ Error Handling

All errors are wrapped in a `QueryBuilderError`:

```ts
try {
  await builder.execute();
} catch (error) {
  if (error instanceof QueryBuilderError) {
    console.error("Query error:", error.originalError);
  }
}
```

---

## 📌 Best Practices

- ✅ Whitelist all filters and sorts explicitly
- ✅ Limit `maxLimit` to protect performance
- ✅ Use `populate()` for referencing related models
- ✅ Use `fixedFilters` for authorization-based querying
- ✅ Alias external query params like `q`, `from`, `to`
- ✅ Standardize query responses across your API

---

## 🧪 Example Query

```http
GET /products?category[in]=electronics,books&price[gte]=50&search=charger&sort=-price&page=1&limit=10&fields=name,price
```

---

## 📚 Result Format

```ts
interface QueryBuilderResult<T> {
  docs: T[];
  meta: {
    total: number;
    page: number;
    limit: number;
    totalPages: number;
    hasNext: boolean;
    hasPrev: boolean;
  };
  links?: {
    first?: string;
    prev?: string;
    next?: string;
    last?: string;
  };
}
```

---

## 🧩 Extending

You can easily extend this builder to:

- Support custom operators
- Add aggregations or group-by logic
- Integrate caching or rate limiting
- Include role-based access logic
