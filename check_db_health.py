"""Database health check script for transcribe-auth"""
import os
import sys
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.models import Base, User, Session

#Database URL
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://admin:changeme@localhost:5432/transcribe"
)

def check_database_health():
    """Check database connectivity and schema health"""
    print("=" * 60)
    print("Database Health Check")
    print("=" * 60)
    print()

    try:
        engine = create_engine(DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()

        #Test 1: Database connectivity
        print("[1/8] Testing database connectivity...")
        try:
            db.execute(text("SELECT 1"))
            print("✓ Database connection successful")
        except Exception as e:
            print(f"✗ Database connection failed: {e}")
            return False

        #Test 2: Check if tables exist
        print("\n[2/8] Checking if tables exist...")
        tables = ['users', 'sessions']
        for table in tables:
            result = db.execute(text(
                f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '{table}')"
            ))
            exists = result.scalar()
            if exists:
                print(f"✓ Table '{table}' exists")
            else:
                print(f"✗ Table '{table}' does not exist")
                return False

        #Test 3: Check indexes
        print("\n[3/8] Checking indexes...")
        indexes = [
            ('users', 'idx_users_username'),
            ('users', 'idx_users_email'),
            ('users', 'idx_users_is_admin'),
            ('sessions', 'idx_sessions_user_id'),
            ('sessions', 'idx_sessions_token'),
            ('sessions', 'idx_sessions_valid')
        ]
        for table, index in indexes:
            result = db.execute(text(
                f"SELECT EXISTS (SELECT FROM pg_indexes WHERE tablename = '{table}' AND indexname = '{index}')"
            ))
            exists = result.scalar()
            if exists:
                print(f"✓ Index '{index}' on '{table}' exists")
            else:
                print(f"⚠ Index '{index}' on '{table}' missing (may be auto-created)")

        #Test 4: Check foreign key constraints
        print("\n[4/8] Checking foreign key constraints...")
        result = db.execute(text("""
            SELECT constraint_name FROM information_schema.table_constraints
            WHERE table_name = 'sessions' AND constraint_type = 'FOREIGN KEY'
        """))
        fk_count = len(result.fetchall())
        if fk_count > 0:
            print(f"✓ Foreign key constraints exist ({fk_count} found)")
        else:
            print("⚠ No foreign key constraints found on sessions table")

        #Test 5: Check user count
        print("\n[5/8] Checking user count...")
        user_count = db.query(User).count()
        admin_count = db.query(User).filter(User.is_admin == True).count()
        active_count = db.query(User).filter(User.is_active == True).count()
        print(f"  Total users: {user_count}")
        print(f"  Admin users: {admin_count}")
        print(f"  Active users: {active_count}")

        #Test 6: Check session count
        print("\n[6/8] Checking session count...")
        total_sessions = db.query(Session).count()
        valid_sessions = db.query(Session).filter(Session.is_valid == True).count()
        active_sessions = db.query(Session).filter(
            Session.is_valid == True,
            Session.expires_at > datetime.utcnow()
        ).count()
        print(f"  Total sessions: {total_sessions}")
        print(f"  Valid sessions: {valid_sessions}")
        print(f"  Active (non-expired) sessions: {active_sessions}")

        #Test 7: Check for orphaned sessions
        print("\n[7/8] Checking for orphaned sessions...")
        orphaned = db.execute(text("""
            SELECT COUNT(*) FROM sessions s
            LEFT JOIN users u ON s.user_id = u.id
            WHERE u.id IS NULL
        """))
        orphaned_count = orphaned.scalar()
        if orphaned_count == 0:
            print(f"✓ No orphaned sessions found")
        else:
            print(f"⚠ Found {orphaned_count} orphaned sessions (sessions without users)")

        #Test 8: Check for expired sessions
        print("\n[8/8] Checking for expired sessions...")
        expired_valid = db.query(Session).filter(
            Session.is_valid == True,
            Session.expires_at <= datetime.utcnow()
        ).count()
        if expired_valid > 0:
            print(f"⚠ Found {expired_valid} expired sessions still marked as valid")
        else:
            print(f"✓ No expired sessions marked as valid")

        #Summary
        print("\n" + "=" * 60)
        print("Database Health Summary")
        print("=" * 60)
        print(f"Database URL: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'localhost'}")
        print(f"Status: ✓ HEALTHY")
        print(f"Users: {user_count} total, {admin_count} admin, {active_count} active")
        print(f"Sessions: {active_sessions} active, {expired_valid} expired but valid")
        print()

        db.close()
        return True

    except Exception as e:
        print(f"\n✗ Health check failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = check_database_health()
    sys.exit(0 if success else 1)
