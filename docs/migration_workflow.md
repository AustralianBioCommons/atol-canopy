
```bash
# Check current migration version
docker compose exec api alembic current

# Rollback one migration
docker compose exec api alembic downgrade -1

# Rollback to specific version
docker compose exec api alembic downgrade <revision_id>

# Restore from backup (last resort)
docker compose exec db psql -U postgres -d atol_db < backup.sql
```

---

## Traditional Server Deployment (Non-Docker Production)

For production environments using VMs, bare metal servers, or Kubernetes (without Docker Compose).

### Setup Requirements

1. **Python environment**
   ```bash
   # Install Python 3.12+ and create virtual environment
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt  # or use uv
   ```

2. **Environment variables**
   ```bash
   # Set database connection in .env or environment
   export DATABASE_URI="postgresql://user:password@db-host:5432/atol_db"
   ```

3. **Alembic configuration**
   - Ensure `alembic.ini` points to correct database
   - Or use environment variable: `ALEMBIC_CONFIG` if needed

### Pre-deployment Checklist

Same as Docker-based deployment, plus:

1. **Verify database connectivity**
   ```bash
   # Test connection from application server
   psql -h db-host -U postgres -d atol_db -c "SELECT version();"
   ```

2. **Check migration files are deployed**
   ```bash
   ls -la alembic/versions/
   # Ensure new migration files are present
   ```

3. **Verify Alembic can connect**
   ```bash
   alembic current
   # Should show current migration version
   ```

### Deployment Steps

#### Option 1: Maintenance Window

1. **Backup database**
   ```bash
   # From database server or application server with access
   pg_dump -h db-host -U postgres -d atol_db -F c -f backup_$(date +%Y%m%d_%H%M%S).dump

   # Or SQL format
   pg_dump -h db-host -U postgres -d atol_db > backup_$(date +%Y%m%d_%H%M%S).sql
   ```

2. **Stop application**
   ```bash
   # Systemd
   sudo systemctl stop atol-api

   # Or supervisor
   sudo supervisorctl stop atol-api

   # Or Kubernetes
   kubectl scale deployment atol-api --replicas=0
   ```

3. **Deploy new code**
   ```bash
   # Pull latest code
   git pull origin main

   # Install dependencies if changed
   pip install -r requirements.txt
   ```

4. **Run migration**
   ```bash
   # Activate virtual environment
   source venv/bin/activate

   # Run migration
   alembic upgrade head

   # Verify
   alembic current
   ```

5. **Start application**
   ```bash
   # Systemd
   sudo systemctl start atol-api

   # Or supervisor
   sudo supervisorctl start atol-api

   # Or Kubernetes
   kubectl scale deployment atol-api --replicas=3
   ```

6. **Monitor**
   ```bash
   # Check logs
   sudo journalctl -u atol-api -f

   # Or supervisor
   sudo tail -f /var/log/atol-api/error.log

   # Or Kubernetes
   kubectl logs -f deployment/atol-api
   ```

#### Option 2: Zero-Downtime (Rolling Deployment)

1. **Ensure migration is backward-compatible**
   - Add columns as nullable
   - Don't drop columns yet
   - Application code works with both old and new schema

2. **Apply migration (while app is running)**
   ```bash
   # SSH to application server or use CI/CD
   source venv/bin/activate
   alembic upgrade head
   ```

3. **Deploy new application code (rolling)**
   ```bash
   # Kubernetes rolling update
   kubectl set image deployment/atol-api api=atol-api:v2.0
   kubectl rollout status deployment/atol-api

   # Or manual rolling restart with load balancer
   # Update server 1, wait, update server 2, etc.
   ```

4. **Verify deployment**
   ```bash
   # Check health endpoint
   curl https://api.example.com/health

   # Monitor logs across all instances
   kubectl logs -l app=atol-api --tail=100
   ```

### Rollback Procedure (Non-Docker)

```bash
# Check current version
alembic current

# Rollback one migration
alembic downgrade -1

# Rollback to specific version
alembic downgrade <revision_id>

# Restore from backup (last resort)
pg_restore -h db-host -U postgres -d atol_db -c backup.dump
# Or for SQL format:
psql -h db-host -U postgres -d atol_db < backup.sql

# Restart application
sudo systemctl restart atol-api
```

### CI/CD Integration

#### GitHub Actions Example

```yaml
# .github/workflows/deploy.yml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt

      - name: Run migrations
        env:
          DATABASE_URI: ${{ secrets.DATABASE_URI }}
        run: |
          alembic upgrade head

      - name: Deploy application
        run: |
          # Your deployment script
          ./deploy.sh
```

#### GitLab CI Example

```yaml
# .gitlab-ci.yml
stages:
  - migrate
  - deploy

migrate:
  stage: migrate
  script:
    - pip install -r requirements.txt
    - alembic upgrade head
  only:
    - main

deploy:
  stage: deploy
  script:
    - ./deploy.sh
  only:
    - main
```

### Kubernetes-Specific Considerations

1. **Use init containers for migrations**
   ```yaml
   apiVersion: apps/v1
   kind: Deployment
   metadata:
     name: atol-api
   spec:
     template:
       spec:
         initContainers:
         - name: migrate
           image: atol-api:latest
           command: ["alembic", "upgrade", "head"]
           env:
           - name: DATABASE_URI
             valueFrom:
               secretKeyRef:
                 name: db-secret
                 key: uri
         containers:
         - name: api
           image: atol-api:latest
   ```

2. **Use Jobs for one-off migrations**
   ```yaml
   apiVersion: batch/v1
   kind: Job
   metadata:
     name: db-migration-v2
   spec:
     template:
       spec:
         containers:
         - name: migrate
           image: atol-api:latest
           command: ["alembic", "upgrade", "head"]
         restartPolicy: Never
   ```

### Production Best Practices (Non-Docker)

1. **Database connection pooling**
   - Use PgBouncer or similar for connection pooling
   - Migrations should use direct connection, not pooler

2. **Migration locks**
   - Alembic uses database locks to prevent concurrent migrations
   - Ensure only one migration process runs at a time

3. **Monitoring**
   ```bash
   # Check migration status
   alembic current

   # View migration history
   alembic history --verbose

   # Check database version
   psql -h db-host -U postgres -d atol_db -c "SELECT * FROM alembic_version;"
   ```

4. **Automated backups before migrations**
   ```bash
   #!/bin/bash
   # pre-migration-backup.sh

   BACKUP_DIR="/backups/db"
   TIMESTAMP=$(date +%Y%m%d_%H%M%S)

   # Create backup
   pg_dump -h db-host -U postgres -d atol_db -F c -f "$BACKUP_DIR/pre_migration_$TIMESTAMP.dump"

   # Run migration
   alembic upgrade head

   # Keep last 7 days of backups
   find $BACKUP_DIR -name "pre_migration_*.dump" -mtime +7 -delete
   ```

5. **Health checks**
   - Ensure health endpoint checks database connectivity
   - Load balancer should remove unhealthy instances during migration

## Migration File Best Practices

### Structure

```python
"""Brief description of what this migration does.

Revision ID: xxxx
Revises: yyyy
Create Date: 2026-02-09

Detailed explanation of changes:
- What tables are affected
- What columns are added/removed
- Any data transformations
"""

def upgrade() -> None:
    # 1. Add new columns as nullable first (for zero-downtime)
    # 2. Migrate data if needed
    # 3. Make columns NOT NULL
    # 4. Add constraints and indexes
    # 5. Drop old columns last
    pass

def downgrade() -> None:
    # Reverse all changes in opposite order
    pass
```

### Tips

- **Idempotent operations**: Use `IF EXISTS` / `IF NOT EXISTS` where possible
- **Data migration**: Include SQL for migrating existing data
- **Indexes**: Create indexes CONCURRENTLY in production to avoid locks
- **Foreign keys**: Add them after data is populated
- **Transactions**: Alembic runs migrations in transactions by default
- **Testing**: Always test both upgrade and downgrade

## Common Patterns

### Adding a Required Column

```python
def upgrade() -> None:
    # Step 1: Add as nullable
    op.add_column('table_name', sa.Column('new_col', sa.Text(), nullable=True))

    # Step 2: Populate with default/migrated data
    op.execute("UPDATE table_name SET new_col = 'default_value'")

    # Step 3: Make NOT NULL
    op.alter_column('table_name', 'new_col', nullable=False)
```

### Renaming a Column

```python
def upgrade() -> None:
    op.alter_column('table_name', 'old_name', new_column_name='new_name')
```

### Dropping a Table with Foreign Keys

```python
def upgrade() -> None:
    # Drop dependent tables/constraints first
    op.drop_constraint('fk_name', 'dependent_table', type_='foreignkey')
    op.drop_table('table_name')
```

## Troubleshooting

### Migration not visible in container
- Ensure `alembic` directory is mounted in `docker-compose.yml`
- Restart containers: `docker compose restart api`

### Migration already applied
- Check: `docker compose exec api alembic current`
- View history: `docker compose exec api alembic history`

### Database connection errors
- Ensure database is running: `docker compose ps`
- Check connection string in `.env`
- Run from within container: `docker compose exec api alembic ...`

### Circular import errors
- Restart containers to clear Python cache
- Check for naming conflicts with Python packages

## Monitoring

After applying migrations in production:

```bash
# Check migration status
docker compose exec api alembic current

# View migration history
docker compose exec api alembic history

# Check database size
docker compose exec db psql -U postgres -d atol_db -c "
  SELECT pg_size_pretty(pg_database_size('atol_db'));"

# Monitor application logs
docker compose logs -f api

# Check for errors
docker compose logs api | grep ERROR
```

## References

- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- Project migrations: `alembic/versions/`
