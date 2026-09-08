#!/usr/bin/env python3
"""
Fetch all models from a dbt Cloud environment.

Cross-platform compatible (macOS, Linux, Windows).

Usage:
    python get_all_models.py [--page-size N] [--filter PATTERN]

Examples:
    python get_all_models.py
    python get_all_models.py --filter "fact_"
    python get_all_models.py --page-size 100
"""

import argparse
import requests
import pandas as pd
import sys
from config import get_config, get_headers, REQUEST_TIMEOUT


def fetch_all_models(
    host: str,
    token: str,
    environment_id: str,
    page_size: int = 500
) -> pd.DataFrame:
    """
    Fetch all models from a dbt Cloud environment using cursor-based pagination.
    
    Parameters:
        host: GraphQL API endpoint URL
        token: Bearer token for authentication
        environment_id: dbt Cloud environment ID
        page_size: Number of records per request (default 500)
    
    Returns:
        DataFrame with columns: uniqueId, name, description
    """
    headers = get_headers(token)
    all_edges = []
    has_next_page = True
    cursor = None
    page_count = 0
    
    # Values are passed as GraphQL variables, never interpolated into the query
    # string. The cursor matters as much as the caller's arguments here: it comes
    # back from the API, so interpolating it lets the response steer the next query.
    query = """
    query Environment($environmentId: BigInt!, $first: Int!, $after: String) {
        environment(id: $environmentId) {
            applied {
                models(first: $first, after: $after) {
                    pageInfo {
                        endCursor
                        hasNextPage
                    }
                    totalCount
                    edges {
                        node {
                            uniqueId
                            name
                            description
                        }
                    }
                }
            }
        }
    }
    """
    
    while has_next_page:
        variables = {
            "environmentId": environment_id,
            "first": page_size,
            "after": cursor,
        }
        
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
        all_edges.extend(models_data['edges'])
        
        has_next_page = models_data['pageInfo']['hasNextPage']
        cursor = models_data['pageInfo']['endCursor']
        page_count += 1
        
        total_count = models_data['totalCount']
        print(f"Page {page_count}: Fetched {len(all_edges)}/{total_count} models", file=sys.stderr)
    
    df = pd.json_normalize(all_edges, sep='_')
    df.columns = [col.replace('node_', '') for col in df.columns]
    
    print(f"\nComplete: {len(df)} models retrieved", file=sys.stderr)
    return df


def main():
    parser = argparse.ArgumentParser(description="Fetch all dbt models from an environment")
    parser.add_argument("--page-size", type=int, default=500, help="Records per API request")
    parser.add_argument("--filter", type=str, help="Filter models by name pattern (case-insensitive)")
    parser.add_argument("--output", type=str, help="Output CSV file path (prints to stdout if omitted)")
    args = parser.parse_args()
    
    config = get_config()
    
    df = fetch_all_models(
        host=config["host"],
        token=config["token"],
        environment_id=config["environment_id"],
        page_size=args.page_size
    )
    
    if args.filter:
        df = df[df['name'].str.contains(args.filter, case=False, na=False)]
        print(f"Filtered to {len(df)} models matching '{args.filter}'", file=sys.stderr)
    
    if args.output:
        df.to_csv(args.output, index=False)
        print(f"Saved to {args.output}", file=sys.stderr)
    else:
        print(df.to_string(index=False))


if __name__ == "__main__":
    main()
