import pytest
import os
from pathlib import Path
import sqlite3

def test_database_initialization():
    """Test if the database can be initialized and tables are created."""
    from services.database import db_init, DB_PATH
    
    # Ensure we use a test database name to not overwrite real data
    test_db = Path("test_iracing_sessions.db")
    if test_db.exists():
        test_db.unlink()
        
    # Mock the DB_PATH in the database module
    import services.database
    original_path = services.database.DB_PATH
    services.database.DB_PATH = test_db
    
    try:
        db_init()
        assert test_db.exists()
        
        # Verify tables
        con = sqlite3.connect(test_db)
        cur = con.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cur.fetchall()]
        assert "sessions" in tables
        assert "setups" in tables
        con.close()
    finally:
        # Cleanup
        if test_db.exists():
            test_db.unlink()
        services.database.DB_PATH = original_path

def test_config_loading():
    """Test if the config file exists and is valid YAML."""
    import yaml
    config_path = Path("config.yaml")
    assert config_path.exists()
    
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    
    assert "app" in config
    assert "version" in config["app"]
    assert config["app"]["title"] == "iRacing Telemetry Analytics"

def test_requirements_file():
    """Test if requirements.txt exists and has content."""
    req_path = Path("requirements.txt")
    assert req_path.exists()
    with open(req_path, "r") as f:
        content = f.read()
        assert len(content) > 0
        assert "numpy" in content
        assert "pandas" in content
