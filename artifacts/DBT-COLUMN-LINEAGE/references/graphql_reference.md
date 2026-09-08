# dbt Cloud Discovery API - GraphQL Reference

Quick reference for column lineage queries. Full documentation: https://docs.getdbt.com/docs/dbt-cloud-apis/discovery-api

## Key Query Patterns

### List All Models
```graphql
query Environment {
    environment(id: ENVIRONMENT_ID) {
        applied {
            models(first: 100, after: "cursor") {
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

### Get Model Details with SQL
```graphql
query Environment {
    environment(id: "ENVIRONMENT_ID") {
        applied {
            models(filter: { uniqueIds: ["model.PROJECT.model_name"] }, first: 1) {
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
query Environment {
    environment(id: "ENVIRONMENT_ID") {
        applied {
            models(filter: { uniqueIds: ["model.PROJECT.model_name"] }, first: 1) {
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
query Column {
    column(environmentId: "ENVIRONMENT_ID") {
        lineage(
            nodeUniqueId: "model.PROJECT.model_name"
            filters: { columnName: "COLUMN_NAME" }
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
