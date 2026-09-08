# dbt Cloud Discovery API - GraphQL Reference

Quick reference for column lineage queries. Full documentation: https://docs.getdbt.com/docs/dbt-cloud-apis/discovery-api

## Passing values

Every query below takes its values as **GraphQL variables**, not as text
interpolated into the query string. The scripts in `scripts/` do the same.

Interpolating is not merely untidy. A model or column name containing a double
quote closes the string literal and rewrites the structure of the query, and the
pagination cursor is attacker-adjacent in the same way because it arrives in the
API's own response. Variables are also the only way to get the types right:
`environmentId` is a `BigInt`, so quoting it as a string is wrong.

```json
{ "query": "<the query>", "variables": { "environmentId": 123456 } }
```

## Key Query Patterns

### List All Models
```graphql
query Environment($environmentId: BigInt!, $first: Int!, $after: String) {
    environment(id: $environmentId) {
        applied {
            models(first: $first, after: $after) {
                pageInfo { endCursor, hasNextPage }
                totalCount
                edges {
                    node { uniqueId, name, description }
                }
            }
        }
    }
}
```

Pass `"after": null` for the first page, then the previous page's `endCursor`.

### Get Model Details with SQL
```graphql
query Environment($environmentId: BigInt!, $uniqueIds: [String!]) {
    environment(id: $environmentId) {
        applied {
            models(filter: { uniqueIds: $uniqueIds }, first: 1) {
                edges {
                    node { rawCode, uniqueId, version, schema, name, description }
                }
            }
        }
    }
}
```

### Get Model Columns
```graphql
query Environment($environmentId: BigInt!, $uniqueIds: [String!]) {
    environment(id: $environmentId) {
        applied {
            models(filter: { uniqueIds: $uniqueIds }, first: 1) {
                edges {
                    node {
                        catalog {
                            columns { name, type, description }
                        }
                    }
                }
            }
        }
    }
}
```

### Get Column Lineage
```graphql
query Column($environmentId: BigInt!, $nodeUniqueId: String!, $columnName: String!) {
    column(environmentId: $environmentId) {
        lineage(
            nodeUniqueId: $nodeUniqueId
            filters: { columnName: $columnName }
        ) {
            name
            nodeUniqueId
            parentColumns
            childColumns
            transformationType
            description
            isPrimaryKey
        }
    }
}
```

## Lineage Response Fields

| Field | Description |
|-------|-------------|
| `name` | Column name |
| `nodeUniqueId` | Parent model's unique ID |
| `uniqueId` | Full column unique ID |
| `parentColumns` | Array of upstream column unique IDs |
| `childColumns` | Array of downstream column unique IDs |
| `transformationType` | How column is derived (e.g., `passthrough`, `transformed`) |
| `description` | Column description from dbt |
| `isPrimaryKey` | Boolean flag |

## Unique ID Format

Models: `model.{PROJECT}.{model_name}`
Columns: `model.{PROJECT}.{model_name}.{COLUMN_NAME}`
Sources: `source.{PROJECT}.{source_name}.{table_name}`
