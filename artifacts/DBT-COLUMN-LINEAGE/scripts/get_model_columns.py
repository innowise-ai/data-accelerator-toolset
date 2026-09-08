#!/usr/bin/env python3
"""
Fetch all columns for a specific dbt model.

Cross-platform compatible (macOS, Linux, Windows).

Usage:
    python get_model_columns.py <unique_id>

Examples:
    python get_model_columns.py model.DBT.fact_orders
    python get_model_columns.py model.DBT.agg_account_ledger_summary --filter "id"
"""

import argparse
import requests
import pandas as pd
import sys
from config import get_config, get_headers


def fetch_model_columns(
    host: str,
    token: str,
    environment_id: str,
    unique_id: str
) -> pd.DataFrame:
    """
    Fetch all columns for a specific dbt model from the catalog.
    
    Parameters:
        host: GraphQL API endpoint URL
        token: Bearer token for authentication
        environment_id: dbt Cloud environment ID
        unique_id: Full unique ID of the model (e.g., model.DBT.fact_orders)
    
    Returns:
        DataFrame with columns: name, type, description
    """
    headers = get_headers(token)
    
    query = f"""
    query Environment {{
        environment(id: "{environment_id}") {{
            applied {{
                models(
                    filter: {{ uniqueIds: ["{unique_id}"] }}
                    first: 1
                ) {{
                    totalCount
                    edges {{
                        node {{
                            name
                            catalog {{
                                columns {{
                                    description
                                    name
                                    type
                                }}
                            }}
                        }}
                    }}
                }}
            }}
        }}
    }}
    """
    
    response = requests.post(host, json={"query": query}, headers=headers)
    response.raise_for_status()
    
    data = response.json()
    
    if "errors" in data:
        raise Exception(f"GraphQL errors: {data['errors']}")
    
    models_data = data['data']['environment']['applied']['models']
    
    if models_data['totalCount'] == 0:
        raise ValueError(f"Model not found: {unique_id}")
    
    node = models_data['edges'][0]['node']
    model_name = node['name']
    
    if not node['catalog'] or not node['catalog']['columns']:
        print(f"Warning: No catalog columns found for {unique_id}", file=sys.stderr)
        return pd.DataFrame(columns=['name', 'type', 'description'])
    
    columns = node['catalog']['columns']
    df = pd.DataFrame(columns)
    
    print(f"Retrieved {len(df)} columns from model '{model_name}'", file=sys.stderr)
    return df


def main():
    parser = argparse.ArgumentParser(description="Fetch columns for a specific dbt model")
    parser.add_argument("unique_id", help="Full unique ID (e.g., model.DBT.fact_orders)")
    parser.add_argument("--filter", type=str, help="Filter columns by name pattern (case-insensitive)")
    parser.add_argument("--output", type=str, help="Output CSV file path")
    args = parser.parse_args()
    
    config = get_config()
    
    df = fetch_model_columns(
        host=config["host"],
        token=config["token"],
        environment_id=config["environment_id"],
        unique_id=args.unique_id
    )
    
    if args.filter:
        df = df[df['name'].str.contains(args.filter, case=False, na=False)]
        print(f"Filtered to {len(df)} columns matching '{args.filter}'", file=sys.stderr)
    
    if args.output:
        df.to_csv(args.output, index=False)
        print(f"Saved to {args.output}", file=sys.stderr)
    else:
        print(df.to_string(index=False))


if __name__ == "__main__":
    main()
