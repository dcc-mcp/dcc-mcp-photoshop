"""dcc-mcp-photoshop server entry point.

Starts the MCP HTTP server + WebSocket bridge server as a standalone process.
No Photoshop or Python SDK required by the end user.

Usage:
    python -m dcc_mcp_photoshop          # default ports
    python -m dcc_mcp_photoshop --help
    dcc-mcp-photoshop                    # if installed via pip (entry-point)
    ./dcc-mcp-photoshop.exe              # if packaged with PyInstaller
"""

from dcc_mcp_photoshop.cli import main

if __name__ == "__main__":
    main()
