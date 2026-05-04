"""
iRacing Telemetry Analytics — Main Entry Point
Run this file to start the Dash dashboard.
"""

from app import app, IBT_OK, DB_PATH
import os

if __name__ == "__main__":
    print("+--------------------------------------------------+")
    print("|  iRacing Telemetry Analytics  v9.1               |")
    print("|  Starting via main.py...                         |")
    print("+--------------------------------------------------+")
    
    if not IBT_OK:
        print("⚠️  Warning: ibt_parser.py not found or import failed.")
    
    print(f"  Database:      {DB_PATH}")
    print("\nURL:  http://127.0.0.1:8050\n")
    
    # Run the Dash server
    # debug=True can be used for development
    app.run(debug=False, port=8050)
