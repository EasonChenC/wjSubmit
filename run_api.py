"""
API Server Launcher with Windows Playwright Fix

This script ensures the correct event loop policy is set before starting the server.
"""

import sys
import asyncio
import os

# CRITICAL: Must set event loop policy BEFORE importing FastAPI/Playwright
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    print("[INFO] Windows detected - Using SelectorEventLoop for Playwright compatibility")

# Now import and run uvicorn
import uvicorn

if __name__ == "__main__":
    # Check if we're in development mode
    dev_mode = os.getenv("DEV_MODE", "true").lower() == "true"

    if dev_mode:
        print("[INFO] Running in development mode (reload disabled for Playwright compatibility)")
        print("[INFO] To enable hot reload, manually restart the server after code changes")

    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,  # Disable reload to avoid subprocess issues
        log_level="info"
    )

