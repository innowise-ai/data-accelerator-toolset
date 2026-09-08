#!/usr/bin/env python3
"""
Fetch details for a specific dbt model including raw SQL code.

Cross-platform compatible (macOS, Linux, Windows).

Usage:
    python get_model.py <unique_id>
    python get_model.py model.DBT.fact_orders

Examples:
    python get_model.py model.DBT.fact_orders
    python get_model.py model.DBT.agg_account_ledger_summary --show-sql
"""

import argparse
import requests
import pandas as pd
import sys
from config import get_config, get_headers, REQUEST_TIMEOUT


def fetch_model(
    host: str,
    token: str,
    environment_id: str,
    unique_id: str
) -> dict:
    """
    Fetch details for a specific dbt model.
    
    Parameters:
        host: GraphQL API endpoint URL
        token: Bearer token for authentication
        environment_id: dbt Cloud environment ID
        unique_id: Full unique ID of the model (e.g., model.DBT.fact_orders)
    
    Returns:
        dict containing: rawCode, uniqueId, version, schema, name, description
    """
    headers = get_headers(token)
    
    # Values are passed as GraphQL variables, never interpolated into the query
    # string. This also fixes the environment id type: the schema declares it as
    # BigInt, so quoting it as a string was wrong.
    query = """
    query Environment($environmentId: BigInt!, $uniqueIds: [String!]) {
        environment(id: $environmentId) {
            applied {
                models(
                    filter: { uniqueIds: $uniqueIds }
                    first: 1
                ) {
                    totalCount
                    edges {
                        node {
                            rawCode
                            uniqueId
                            version
                            schema
                            name
                            description
                        }
                    }
                }
            }
        }
    }
    """
    
    variables = {"environmentId": environment_id, "uniqueIds": [unique_id]}
    
    response = requests.post(
        host,
        json={"query": query, "variables": variables},
        headers=headers,
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    
    data = response.json()
    
    if "errors" in data:
        raise Exception(f"GraphQL errors: {data['errors']}")
    
    models_data = data['data']['environment']['applied']['models']
    
    if models_data['totalCount'] == 0:
        raise ValueError(f"Model not found: {unique_id}")
    
    model = models_data['edges'][0]['node']
    print(f"Retrieved model: {model['name']} ({model['uniqueId']})", file=sys.stderr)
    
    return model


def main():
    parser = argparse.ArgumentParser(description="Fetch details for a specific dbt model")
    parser.add_argument("unique_id", help="Full unique ID (e.g., model.DBT.fact_orders)")
    parser.add_argument("--show-sql", action="store_true", help="Display the raw SQL code")
    args = parser.parse_args()
    
    config = get_config()
    
    model = fetch_model(
        host=config["host"],
        token=config["token"],
        environment_id=config["environment_id"],
        unique_id=args.unique_id
    )
    
    print(f"\n{'='*60}")
    print(f"Model: {model['name']}")
    print(f"Unique ID: {model['uniqueId']}")
    print(f"Schema: {model['schema']}")
    print(f"Version: {model['version']}")
    print(f"{'='*60}")
    
    if model['description']:
        print(f"\nDescription:\n{model['description']}")
    
    if args.show_sql:
        print(f"\n{'='*60}")
        print("Raw SQL Code:")
        print(f"{'='*60}")
        print(model['rawCode'])


if __name__ == "__main__":
    main()
