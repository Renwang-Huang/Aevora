"""MCP test wrapper: lower the public wire budget to force continuation pages."""
import os

import aevora.mcp_projection as projection


projection.WIRE_BUDGET = int(os.environ.get("G24_PAGINATION_WIRE_BUDGET", "12000"))

from aevora.mcp_server import main


if __name__ == "__main__":
    raise SystemExit(main())
