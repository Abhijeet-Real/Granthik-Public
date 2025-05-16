"""
Script to run the groups migration
"""
from app.db.migrations.ensure_groups import run_migration

if __name__ == "__main__":
    run_migration()