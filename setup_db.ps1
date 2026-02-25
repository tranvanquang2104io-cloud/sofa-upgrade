# PowerShell script to set up PostgreSQL database for SofaFlow
# Run this as Administrator or with proper PostgreSQL admin credentials

param(
    [string]$PostgresHost = "localhost",
    [int]$PostgresPort = 5432,
    [string]$PostgresUser = "postgres",
    [string]$PostgresPassword = "",
    [string]$SqlFile = "setup_db.sql"
)

Write-Host "SofaFlow Database Setup Script" -ForegroundColor Green
Write-Host "===============================" -ForegroundColor Green
Write-Host ""

# Check if psql is available
$psqlPath = "C:\Program Files\PostgreSQL\15\bin\psql.exe"
if (!(Test-Path $psqlPath)) {
    $psqlPath = "C:\Program Files\PostgreSQL\14\bin\psql.exe"
}
if (!(Test-Path $psqlPath)) {
    $psqlPath = "C:\Program Files\PostgreSQL\13\bin\psql.exe"
}
if (!(Test-Path $psqlPath)) {
    Write-Host "ERROR: psql not found. Please make sure PostgreSQL is installed." -ForegroundColor Red
    Write-Host "Searched locations:" -ForegroundColor Red
    Write-Host "  - C:\Program Files\PostgreSQL\15\bin\psql.exe" -ForegroundColor Red
    Write-Host "  - C:\Program Files\PostgreSQL\14\bin\psql.exe" -ForegroundColor Red
    Write-Host "  - C:\Program Files\PostgreSQL\13\bin\psql.exe" -ForegroundColor Red
    exit 1
}

Write-Host "Found psql at: $psqlPath" -ForegroundColor Green
Write-Host ""

# Check if SQL file exists
if (!(Test-Path $SqlFile)) {
    Write-Host "ERROR: $SqlFile not found. Please make sure you're in the project directory." -ForegroundColor Red
    exit 1
}

Write-Host "Executing database setup SQL..."
Write-Host ""

# If password is provided, use it; otherwise use connection without password (trusted connection)
if ($PostgresPassword) {
    $env:PGPASSWORD = $PostgresPassword
    & $psqlPath -h $PostgresHost -p $PostgresPort -U $PostgresUser -f $SqlFile
    $env:PGPASSWORD = ""
} else {
    & $psqlPath -h $PostgresHost -p $PostgresPort -U $PostgresUser -f $SqlFile
}

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Database setup completed successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "You can now run: python init_db.py" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "ERROR: Database setup failed with exit code $LASTEXITCODE" -ForegroundColor Red
    Write-Host ""
    Write-Host "Troubleshooting:" -ForegroundColor Yellow
    Write-Host "1. Verify PostgreSQL is running" -ForegroundColor Yellow
    Write-Host "2. Check PostgreSQL username and password" -ForegroundColor Yellow
    Write-Host "3. Ensure you have admin privileges in PostgreSQL" -ForegroundColor Yellow
}

exit $LASTEXITCODE
