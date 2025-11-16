#!/usr/bin/env python3
"""Simple database connectivity test using psycopg2"""
import os
import psycopg2
from psycopg2 import sql
from urllib.parse import urlparse

#Database URL from environment or default
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://admin:changeme@localhost:5432/transcribe"
)

def parse_database_url(url):
    """Parse PostgreSQL URL into connection parameters"""
    parsed = urlparse(url)
    return {
        'host': parsed.hostname,
        'port': parsed.port or 5432,
        'database': parsed.path[1:],  #Remove leading slash
        'user': parsed.username,
        'password': parsed.password
    }

def test_database_connection():
    """Test database connection and verify schema"""
    print("=" * 60)
    print("PostgreSQL Database Connection Test")
    print("=" * 60)
    print()

    try:
        #Parse connection URL
        conn_params = parse_database_url(DATABASE_URL)
        print(f"Connecting to: {conn_params['host']}:{conn_params['port']}/{conn_params['database']}")
        print(f"User: {conn_params['user']}")
        print()

        #Connect to database
        conn = psycopg2.connect(**conn_params)
        conn.set_session(autocommit=True)
        cur = conn.cursor()

        #Test 1: Basic connectivity
        print("[1/6] Testing database connectivity...")
        cur.execute("SELECT version();")
        version = cur.fetchone()[0]
        print(f"✓ Connected to PostgreSQL")
        print(f"  Version: {version.split(',')[0]}")

        #Test 2: Check database exists
        print("\n[2/6] Checking database...")
        cur.execute("SELECT current_database();")
        db_name = cur.fetchone()[0]
        print(f"✓ Database: {db_name}")

        #Test 3: Check tables exist
        print("\n[3/6] Checking tables...")
        cur.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        tables = cur.fetchall()
        if tables:
            print(f"✓ Found {len(tables)} table(s):")
            for table in tables:
                print(f"  - {table[0]}")
        else:
            print("⚠ No tables found (database needs initialization)")

        #Test 4: Check indexes
        print("\n[4/6] Checking indexes...")
        cur.execute("""
            SELECT schemaname, tablename, indexname
            FROM pg_indexes
            WHERE schemaname = 'public'
            ORDER BY tablename, indexname;
        """)
        indexes = cur.fetchall()
        if indexes:
            print(f"✓ Found {len(indexes)} index(es)")
            index_dict = {}
            for schema, table, index in indexes:
                if table not in index_dict:
                    index_dict[table] = []
                index_dict[table].append(index)
            for table, idxs in index_dict.items():
                print(f"  Table '{table}': {len(idxs)} indexes")
        else:
            print("⚠ No indexes found")

        #Test 5: Check users table structure (if exists)
        print("\n[5/6] Checking 'users' table structure...")
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'users'
            );
        """)
        users_exists = cur.fetchone()[0]
        if users_exists:
            cur.execute("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_name = 'users'
                ORDER BY ordinal_position;
            """)
            columns = cur.fetchall()
            print(f"✓ 'users' table has {len(columns)} columns:")
            for col_name, data_type, nullable, default in columns:
                null_str = "NULL" if nullable == "YES" else "NOT NULL"
                default_str = f" DEFAULT {default}" if default else ""
                print(f"  - {col_name}: {data_type} {null_str}{default_str}")
        else:
            print("⚠ 'users' table does not exist")

        #Test 6: Check sessions table structure (if exists)
        print("\n[6/6] Checking 'sessions' table structure...")
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'sessions'
            );
        """)
        sessions_exists = cur.fetchone()[0]
        if sessions_exists:
            cur.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'sessions'
                ORDER BY ordinal_position;
            """)
            columns = cur.fetchall()
            print(f"✓ 'sessions' table has {len(columns)} columns:")
            for col_name, data_type, nullable in columns:
                null_str = "NULL" if nullable == "YES" else "NOT NULL"
                print(f"  - {col_name}: {data_type} {null_str}")
        else:
            print("⚠ 'sessions' table does not exist")

        #Summary
        print("\n" + "=" * 60)
        print("Connection Test Summary")
        print("=" * 60)
        print(f"✓ Database connection: SUCCESSFUL")
        print(f"✓ Database name: {db_name}")
        print(f"✓ Tables found: {len(tables)}")
        print(f"✓ Indexes found: {len(indexes)}")

        if not tables:
            print("\n⚠ Database needs initialization. Run init_db.sql")

        cur.close()
        conn.close()
        return True

    except psycopg2.OperationalError as e:
        print(f"✗ Connection failed: {e}")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import sys
    success = test_database_connection()
    sys.exit(0 if success else 1)
