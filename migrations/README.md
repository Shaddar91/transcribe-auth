# Database Migrations

This directory contains SQL migration scripts for the transcribe-auth database.

## Migration Files

Migrations are numbered sequentially and should be applied in order:

- `001_add_admin_field.sql` - Adds is_admin column to users table for admin role support

## How to Apply Migrations

### Using Docker Compose

```bash
# Connect to the database container
docker-compose exec postgres psql -U admin -d transcribe

# Run a migration
\i /docker-entrypoint-initdb.d/migrations/001_add_admin_field.sql
```

### Using psql directly

```bash
# Apply a single migration
psql -U admin -d transcribe -f migrations/001_add_admin_field.sql

# Apply all migrations in order
for file in migrations/*.sql; do
    echo "Applying $file"
    psql -U admin -d transcribe -f "$file"
done
```

### From within the auth-service container

```bash
docker-compose exec auth-service python migrations/apply_migrations.py
```

## Creating New Migrations

1. Create a new file with sequential numbering: `NNN_description.sql`
2. Include idempotent checks (IF NOT EXISTS, etc.)
3. Add comments describing what the migration does
4. Test the migration locally before deploying

## Migration Best Practices

1. **Idempotent**: Migrations should be safe to run multiple times
2. **Backward Compatible**: Don't break existing functionality
3. **Documented**: Include clear comments about what changes
4. **Tested**: Test locally before production
5. **Sequential**: Number migrations in order of application
6. **Atomic**: Use transactions where possible

## Rollback Strategy

For each migration, consider creating a corresponding rollback script:
- `NNN_description.sql` - Forward migration
- `NNN_description_rollback.sql` - Rollback migration

## Production Deployment

Before deploying to production:

1. Backup the database
2. Test migrations on staging environment
3. Plan maintenance window if needed
4. Apply migrations during low-traffic period
5. Verify application functionality after migration
6. Monitor for errors
