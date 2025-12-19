# PowerShell script to restore all database tables

Write-Host "Step 1: Stamping database to version before survey migration..." -ForegroundColor Yellow
alembic stamp f9218dd57616

Write-Host "Step 2: Running all migrations from that point..." -ForegroundColor Yellow
alembic upgrade head

Write-Host "Done! All tables should now be restored." -ForegroundColor Green









