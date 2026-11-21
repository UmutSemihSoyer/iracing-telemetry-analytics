"""
iRacing Telemetry Analytics — Main Entry Point
Run this file to start the Dash dashboard.
"""

from app import app, IBT_OK, DB_PATH
import os

import sys
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Start the iRacing Telemetry Analytics Dashboard")
    parser.add_argument("--port", type=int, default=8050, help="Port to run the dashboard on (default: 8050)")
    args, unknown = parser.parse_known_args()
    
    # Simple fallback if user runs `python main.py -port8051`
    for arg in unknown:
        if arg.startswith("-port"):
            try:
                args.port = int(arg.replace("-port", "").replace(":", ""))
            except ValueError:
                pass

    print("+--------------------------------------------------+")
    print("|  iRacing Telemetry Analytics  v9.1               |")
    print("|  Starting via main.py...                         |")
    print("+--------------------------------------------------+")
    
    if not IBT_OK:
        print("⚠️  Warning: ibt_parser.py not found or import failed.")
    
    print(f"  Database:      {DB_PATH}")
    print("\n[TIP] For the Professional Desktop Edition, run 'Launch_Desktop.bat'")
    print(f"URL:  http://127.0.0.1:{args.port}\n")
    
    # Run the Dash server
    # debug=True can be used for development
    app.run(debug=False, port=args.port)
