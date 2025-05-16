"""
Script to run all migrations in order
"""
import os
import importlib.util
import sys

def run_migrations():
    """
    Run all migration scripts in the migrations directory
    """
    print("Starting migrations...")
    
    # Get all Python files in the migrations directory
    migration_files = [f for f in os.listdir(os.path.dirname(__file__)) 
                      if f.endswith('.py') and f != 'run_migrations.py' and f != '__init__.py']
    
    # Sort the files to ensure they run in the correct order
    migration_files.sort()
    
    # Run each migration
    for migration_file in migration_files:
        print(f"\nRunning migration: {migration_file}")
        
        # Import the migration module
        module_name = migration_file[:-3]  # Remove .py extension
        module_path = os.path.join(os.path.dirname(__file__), migration_file)
        
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Run the migration
        if hasattr(module, 'run_migration'):
            module.run_migration()
        else:
            print(f"Warning: {migration_file} does not have a run_migration function")
    
    print("\nAll migrations completed successfully")

if __name__ == "__main__":
    run_migrations()