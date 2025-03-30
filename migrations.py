#!/usr/bin/env python3
"""
Database migration utility for Bulk Email Scheduler
This script will help you manage database migrations when schema changes are needed
"""
import argparse
import sys
import os
from datetime import datetime
import importlib.util
import inspect

# Ensure correct path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import EmailCampaign, EmailRecipient

def create_migration(args):
    """Create a new migration file"""
    name = args.name.lower().replace(' ', '_')
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    
    migration_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'migrations')
    if not os.path.exists(migration_dir):
        os.makedirs(migration_dir)
    
    filename = f"{timestamp}_{name}.py"
    file_path = os.path.join(migration_dir, filename)
    
    with open(file_path, 'w') as f:
        f.write(f'''"""
Migration: {name}
Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
from app import db
from models import EmailCampaign, EmailRecipient

def upgrade():
    """
    Make database schema changes here
    Example:
    db.engine.execute('ALTER TABLE email_campaign ADD COLUMN new_field TEXT')
    """
    # Your migration code here
    pass

def downgrade():
    """
    Code to revert the changes if needed
    Example:
    db.engine.execute('ALTER TABLE email_campaign DROP COLUMN new_field')
    """
    # Your rollback code here
    pass
''')
    
    print(f"Created migration file: {file_path}")

def run_migrations(args):
    """Run pending migrations"""
    migration_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'migrations')
    if not os.path.exists(migration_dir):
        print("No migrations directory found.")
        return
    
    # Get all migration files
    migration_files = sorted([f for f in os.listdir(migration_dir) if f.endswith('.py')])
    
    if not migration_files:
        print("No migration files found.")
        return
    
    # Create migrations_applied table if it doesn't exist
    with app.app_context():
        db.engine.execute('''
        CREATE TABLE IF NOT EXISTS migrations_applied (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            migration_name TEXT NOT NULL,
            applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Get already applied migrations
        result = db.engine.execute('SELECT migration_name FROM migrations_applied')
        applied_migrations = [row[0] for row in result]
        
        # Run pending migrations
        for migration_file in migration_files:
            if migration_file in applied_migrations:
                print(f"Migration {migration_file} already applied, skipping.")
                continue
            
            print(f"Applying migration: {migration_file}")
            
            # Import the migration module
            spec = importlib.util.spec_from_file_location(
                migration_file[:-3],
                os.path.join(migration_dir, migration_file)
            )
            migration_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(migration_module)
            
            # Run the upgrade function
            migration_module.upgrade()
            
            # Mark as applied
            db.engine.execute(
                "INSERT INTO migrations_applied (migration_name) VALUES (?)",
                (migration_file,)
            )
            
            print(f"Applied migration: {migration_file}")
    
    print("All migrations applied successfully!")

def rollback_migration(args):
    """Rollback the last applied migration"""
    migration_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'migrations')
    
    with app.app_context():
        # Check if migrations table exists
        result = db.engine.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='migrations_applied'
        """)
        if not result.fetchone():
            print("No migrations have been applied yet.")
            return
        
        # Get the last applied migration
        result = db.engine.execute("""
            SELECT migration_name FROM migrations_applied 
            ORDER BY applied_at DESC LIMIT 1
        """)
        row = result.fetchone()
        
        if not row:
            print("No migrations have been applied yet.")
            return
        
        last_migration = row[0]
        
        # Import the migration module
        spec = importlib.util.spec_from_file_location(
            last_migration[:-3],
            os.path.join(migration_dir, last_migration)
        )
        migration_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration_module)
        
        # Check if downgrade function exists
        if not hasattr(migration_module, 'downgrade'):
            print(f"Migration {last_migration} does not have a downgrade function.")
            return
        
        print(f"Rolling back migration: {last_migration}")
        
        # Run the downgrade function
        migration_module.downgrade()
        
        # Remove from applied migrations
        db.engine.execute(
            "DELETE FROM migrations_applied WHERE migration_name = ?",
            (last_migration,)
        )
        
        print(f"Rolled back migration: {last_migration}")

def main():
    parser = argparse.ArgumentParser(description='Database migration utility for Bulk Email Scheduler')
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Create migration
    create_parser = subparsers.add_parser('create', help='Create a new migration')
    create_parser.add_argument('name', help='Name of the migration')
    create_parser.set_defaults(func=create_migration)
    
    # Run migrations
    run_parser = subparsers.add_parser('run', help='Run pending migrations')
    run_parser.set_defaults(func=run_migrations)
    
    # Rollback migration
    rollback_parser = subparsers.add_parser('rollback', help='Rollback the last applied migration')
    rollback_parser.set_defaults(func=rollback_migration)
    
    # Parse arguments
    args = parser.parse_args()
    
    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
