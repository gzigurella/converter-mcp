#!/usr/bin/env python3

import sys
import asyncio
from converter.server import main as server_main


def main():
    """Entry point for the converter-mcp command."""
    return asyncio.run(server_main())


if __name__ == "__main__":
    sys.exit(main())
