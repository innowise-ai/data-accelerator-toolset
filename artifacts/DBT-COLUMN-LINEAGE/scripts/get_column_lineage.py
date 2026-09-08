#!/usr/bin/env python3
"""
Trace lineage for a specific column in a dbt model.

Cross-platform compatible (macOS, Linux, Windows).

Usage:
    python get_column_lineage.py <unique_id> <column_name>

Examples:
    python get_column_lineage.py model.DBT.fact_orders NATURAL_JOB_ID
    python get_column_lineage.py model.DBT.fact_orders NATURAL_JOB_ID --tree
"""

import argparse
import requests
import pandas as pd
import sys
from config import get_config, get_headers, REQUEST_TIMEOUT


def fetch_column_lineage(
    host: str,
    token: str,
    environment_id: str,
    unique_id: str,
    column_name: str
) -> pd.DataFrame:
    """
    Fetch lineage information for a specific column in a dbt model.
    
    Parameters:
        host: GraphQL API endpoint URL
        token: Bearer token for authentication
        environment_id: dbt Cloud environment ID
        unique_id: Full unique ID of the model (e.g., model.DBT.fact_orders)
        column_name: Name of the column to trace (case-sensitive)
    
    Returns:
        DataFrame with lineage information including parent/child columns
    """
    headers = get_headers(token)
    
    # Values are passed as GraphQL variables, never interpolated into the query
    # string. A column name containing a double quote would otherwise close the
    # string literal and rewrite the query structure.
    query = """
    query Column($environmentId: BigInt!, $nodeUniqueId: String!, $columnName: String!) {
        column(environmentId: $environmentId) {
            lineage(
                nodeUniqueId: $nodeUniqueId
                filters: { columnName: $columnName }
            ) {
                description
                descriptionOriginColumnName
                isPrimaryKey
                name
                nodeUniqueId
                parentColumns
                childColumns
                projectId
                relationship
                uniqueId
                transformationType
            }
        }
    }
    """
    
    variables = {
        "environmentId": environment_id,
        "nodeUniqueId": unique_id,
        "columnName": column_name,
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
    
    lineage = data['data']['column']['lineage']
    
    if not lineage:
        print(f"No lineage found for column '{column_name}' in {unique_id}", file=sys.stderr)
        return pd.DataFrame()
    
    df = pd.DataFrame(lineage)
    print(f"Retrieved lineage with {len(df)} nodes", file=sys.stderr)
    
    return df


def display_tree(df: pd.DataFrame, target_unique_id: str, target_column: str):
    """
    Display lineage as an indented tree structure.
    
    Parameters:
        df: DataFrame with lineage data
        target_unique_id: The model we're tracing from
        target_column: The column we're tracing
    """
    if df.empty:
        print("No lineage data to display")
        return
    
    # Build lookup for easy access
    # Convert each row to a dict to avoid pandas Series truthiness issues
    nodes = {row['uniqueId']: dict(row) for _, row in df.iterrows()}
    
    def get_model_name(unique_id: str) -> str:
        """Extract model name from uniqueId like 'model.DBT.fact_orders.COLUMN'"""
        parts = unique_id.split('.')
        if len(parts) >= 3:
            return parts[2]  # model name
        return unique_id
    
    print(f"\n{'='*70}")
    print(f"COLUMN LINEAGE: {target_column}")
    print(f"Starting from: {target_unique_id}")
    print(f"{'='*70}\n")
    
    # Find the target node
    target_node = None
    for uid, node in nodes.items():
        if node['nodeUniqueId'] == target_unique_id and node['name'].upper() == target_column.upper():
            target_node = node
            break
    
    # FIX: Use 'is None' instead of 'not target_node' to avoid pandas Series ambiguity
    if target_node is None:
        # Just display all nodes if we can't find the target
        print("Lineage nodes:")
        for _, row in df.iterrows():
            model_name = get_model_name(row['nodeUniqueId'])
            transformation = row.get('transformationType', 'unknown')
            print(f"  [{model_name}].{row['name']} ({transformation})")
            if row.get('parentColumns'):
                print(f"    └─ Parents: {row['parentColumns']}")
        return
    
    # Display upstream lineage (parents)
    print("UPSTREAM (where this column comes from):")
    print("-" * 40)
    
    visited = set()
    def print_upstream(node, indent=0):
        uid = node.get('uniqueId', '')
        if uid in visited:
            return
        visited.add(uid)
        
        model_name = get_model_name(node['nodeUniqueId'])
        col_name = node['name']
        transformation = node.get('transformationType', '')
        prefix = "  " * indent
        
        marker = "→ " if indent == 0 else "└─ "
        trans_info = f" [{transformation}]" if transformation else ""
        print(f"{prefix}{marker}[{model_name}].{col_name}{trans_info}")
        
        parents = node.get('parentColumns', [])
        if parents:
            for parent_uid in parents:
                if parent_uid in nodes:
                    print_upstream(nodes[parent_uid], indent + 1)
                else:
                    # Parent not in our result set - just show the ID
                    print(f"{prefix}  └─ {parent_uid}")
    
    print_upstream(target_node)
    
    # Display downstream lineage (children)
    print(f"\nDOWNSTREAM (what depends on this column):")
    print("-" * 40)
    
    visited.clear()
    def print_downstream(node, indent=0):
        uid = node.get('uniqueId', '')
        if uid in visited:
            return
        visited.add(uid)
        
        model_name = get_model_name(node['nodeUniqueId'])
        col_name = node['name']
        transformation = node.get('transformationType', '')
        prefix = "  " * indent
        
        marker = "→ " if indent == 0 else "└─ "
        trans_info = f" [{transformation}]" if transformation else ""
        print(f"{prefix}{marker}[{model_name}].{col_name}{trans_info}")
        
        children = node.get('childColumns', [])
        if children:
            for child_uid in children:
                if child_uid in nodes:
                    print_downstream(nodes[child_uid], indent + 1)
                else:
                    print(f"{prefix}  └─ {child_uid}")
    
    print_downstream(target_node)


def main():
    parser = argparse.ArgumentParser(description="Trace lineage for a dbt column")
    parser.add_argument("unique_id", help="Full model unique ID (e.g., model.DBT.fact_orders)")
    parser.add_argument("column_name", help="Column name to trace (case-sensitive)")
    parser.add_argument("--tree", action="store_true", help="Display as indented tree structure")
    parser.add_argument("--output", type=str, help="Output CSV file path")
    args = parser.parse_args()
    
    config = get_config()
    
    df = fetch_column_lineage(
        host=config["host"],
        token=config["token"],
        environment_id=config["environment_id"],
        unique_id=args.unique_id,
        column_name=args.column_name
    )
    
    if df.empty:
        sys.exit(0)
    
    if args.tree:
        display_tree(df, args.unique_id, args.column_name)
    elif args.output:
        df.to_csv(args.output, index=False)
        print(f"Saved to {args.output}", file=sys.stderr)
    else:
        # Display key columns in a readable format
        display_cols = ['name', 'nodeUniqueId', 'transformationType', 'parentColumns', 'childColumns']
        available_cols = [c for c in display_cols if c in df.columns]
        print(df[available_cols].to_string(index=False))


if __name__ == "__main__":
    main()
