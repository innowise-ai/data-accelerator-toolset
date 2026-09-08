"""
Shared configuration for dbt Cloud Discovery API scripts.

Cross-platform compatible (macOS, Linux, Windows).

Required environment variables:
    DBT_CLOUD_HOST: GraphQL API endpoint (e.g., https://metadata.cloud.getdbt.com/beta/graphql)
    DBT_CLOUD_ENVIRONMENT_ID: dbt Cloud environment ID (numeric)
    DBT_CLOUD_TOKEN: Bearer token for authentication

Configuration should be set via shell environment variables:
    - macOS/Linux: Add exports to ~/.zshrc or ~/.bashrc
    - Windows: Set via System Environment Variables or PowerShell profile
"""

import os
import sys
import platform
from pathlib import Path

# Seconds to wait on a Discovery API call before giving up. Without a timeout a
# stalled connection hangs the script indefinitely, and Desktop Commander's own
# timeout_ms would kill it with no diagnostic.
REQUEST_TIMEOUT = 30


def get_platform_info() -> dict:
    """
    Get information about the current platform.
    
    Returns:
        dict with keys: os_name, is_windows, is_macos, is_linux, shell_config_hint
    """
    system = platform.system().lower()
    
    info = {
        "os_name": platform.system(),
        "is_windows": system == "windows",
        "is_macos": system == "darwin",
        "is_linux": system == "linux",
    }
    
    # Provide helpful hints for shell configuration
    if info["is_windows"]:
        info["shell_config_hint"] = "PowerShell profile ($PROFILE) or System Environment Variables"
    elif info["is_macos"]:
        info["shell_config_hint"] = "~/.zshrc (default on macOS) or ~/.bash_profile"
    else:
        info["shell_config_hint"] = "~/.bashrc or ~/.profile"
    
    return info


def get_config() -> dict:
    """
    Load configuration from environment variables.
    
    Works cross-platform (macOS, Linux, Windows). Environment variables
    should be set in your shell configuration file or system settings.
    
    Returns:
        dict with keys: host, environment_id, token
    
    Raises:
        SystemExit if required variables are missing
    """
    required_vars = {
        "DBT_CLOUD_HOST": "GraphQL API endpoint URL",
        "DBT_CLOUD_ENVIRONMENT_ID": "dbt Cloud environment ID",
        "DBT_CLOUD_TOKEN": "Bearer token for authentication"
    }
    
    missing = []
    for var, description in required_vars.items():
        if not os.environ.get(var):
            missing.append(f"  - {var}: {description}")
    
    if missing:
        platform_info = get_platform_info()
        
        print("ERROR: Missing required environment variables:", file=sys.stderr)
        print("\n".join(missing), file=sys.stderr)
        print(f"\nDetected platform: {platform_info['os_name']}", file=sys.stderr)
        print(f"Configuration location: {platform_info['shell_config_hint']}", file=sys.stderr)
        
        print("\n" + "="*60, file=sys.stderr)
        print("SETUP INSTRUCTIONS", file=sys.stderr)
        print("="*60, file=sys.stderr)
        
        if platform_info["is_windows"]:
            print("""
For Windows PowerShell, add to your $PROFILE:

    $env:DBT_CLOUD_HOST = "https://metadata.cloud.getdbt.com/beta/graphql"
    $env:DBT_CLOUD_ENVIRONMENT_ID = "your_environment_id"
    $env:DBT_CLOUD_TOKEN = "your_bearer_token"
    $env:SKILL_SCRIPTS_PATH = "C:\\path\\to\\scripts"

Or set System Environment Variables via Control Panel.
""", file=sys.stderr)
        else:
            shell_file = "~/.zshrc" if platform_info["is_macos"] else "~/.bashrc"
            print(f"""
Add these lines to {shell_file}:

    export DBT_CLOUD_HOST="https://metadata.cloud.getdbt.com/beta/graphql"
    export DBT_CLOUD_ENVIRONMENT_ID="your_environment_id"
    export DBT_CLOUD_TOKEN="your_bearer_token"
    export SKILL_SCRIPTS_PATH="/path/to/scripts"

Then reload your shell:
    source {shell_file}

Note: When using Desktop Commander, always prefix commands with:
    source {shell_file} && python3 script.py
""", file=sys.stderr)
        
        sys.exit(1)
    
    return {
        "host": os.environ["DBT_CLOUD_HOST"],
        "environment_id": os.environ["DBT_CLOUD_ENVIRONMENT_ID"],
        "token": os.environ["DBT_CLOUD_TOKEN"]
    }


def get_headers(token: str) -> dict:
    """Return authorization headers for API requests."""
    return {"Authorization": f"Bearer {token}"}


def get_python_command() -> str:
    """
    Get the appropriate Python command for the current platform.
    
    Returns:
        'python3' on macOS/Linux, 'python' on Windows
    """
    platform_info = get_platform_info()
    return "python" if platform_info["is_windows"] else "python3"
