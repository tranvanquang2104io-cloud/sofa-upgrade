<#
.SYNOPSIS
    SofaFlow — Rollback tự động về version cũ
    Backup DB hiện tại → Khôi phục code → Docker rebuild → Health check
    Tuỳ chọn: khôi phục cả database từ backup file

.PARAMETER ToVersion
    Version muốn quay về, định dạng x.y.z  (tuỳ chọn)
    Nếu không truyền sẽ hiện menu chọn tương tác
    Ví dụ: 1.0.0

.PARAMETER RestoreDB
    Nếu bật, sẽ hỏi chọn file backup SQL để khôi phục database
    ⚠ NGUY HIỂM: ghi đè toàn bộ dữ liệu hiện tại

.PARAMETER NoDB
    Bỏ qua bước backup DB hiện tại trước khi rollback (không khuyến nghị)

.PARAMETER NoDocker
    Không rebuild Docker sau rollback

.PARAMETER DryRun
    Chạy thử — in ra tất cả bước nhưng KHÔNG thực sự thay đổi gì

.EXAMPLE
    .\scripts\rollback.ps1                          # menu chọn version tương tác
    .\scripts\rollback.ps1 -ToVersion "1.0.0"       # rollback thẳng về 1.0.0
    .\scripts\rollback.ps1 -ToVersion "1.0.0" -RestoreDB  # rollback code + DB
    .\scripts\rollback.ps1 -DryRun                  # xem trước, không làm gì
#>

[CmdletBinding()]
param(
    [string]$ToVersion = "",

    [switch]$RestoreDB,
    [switch]$NoDB,
    [switch]$NoDocker,
    [switch]$DryRun
)

# ─── Helper ────────────────────────────────────────────────────────────────────
function Write-Step { param($n,$t) Write-Host "`n[$n] $t" -ForegroundColor Cyan }
function Write-OK   { param($t)    Write-Host "    ✔  $t" -ForegroundColor Green }
function Write-Warn { param($t)    Write-Host "    ⚠  $t" -ForegroundColor Yellow }
function Write-Fail { param($t)    Write-Host "    ✖  $t" -ForegroundColor Red }
function Write-Info { param($t)    Write-Host "    •  $t" -ForegroundColor Gray }

function Invoke-Step {
    param([string]$Cmd)
    if ($DryRun) { Write-Info "[DryRun] $Cmd"; return }
    Invoke-Expression $Cmd
    if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
        Write-Fail "Lệnh thất bại (exit $LASTEXITCODE): $Cmd"
        exit 1
    }
}

# ─── Tiêu đề ──────────────────────────────────────────────────────────────────
$Line = "═" * 60
Write-Host "`n$Line" -ForegroundColor Red
Write-Host "   ⏪  SofaFlow Rollback Pipeline" -ForegroundColor Red
if ($DryRun) { Write-Host "   [DRY RUN — không có thay đổi thực sự]" -ForegroundColor Yellow }
Write-Host "$Line`n" -ForegroundColor Red

$ProjectRoot = Split-Path $PSScriptRoot -Parent
Set-Location $ProjectRoot

$BackupDir    = Join-Path $ProjectRoot "backups"
$VersionFile  = Join-Path $ProjectRoot "VERSION"
$Timestamp    = Get-Date -Format "yyyyMMdd_HHmmss"

$CurrentVersion = (Get-Content $VersionFile -Encoding UTF8 -ErrorAction SilentlyContinue).Trim()

# ─── Bước 0: Chọn version để rollback về ─────────────────────────────────────
Write-Step "0/6" "Chọn version rollback"

# Lấy danh sách tất cả tags dạng version
$AllTags = git tag --sort=-version:refname 2>$null | Where-Object { $_ -match '^v\d+\.\d+\.\d+$' }

if (-not $AllTags) {
    Write-Fail "Không tìm thấy tag version nào trong git repo này."
    Write-Info "Đảm bảo đã chạy: git fetch --tags"
    exit 1
}

# Nếu không truyền -ToVersion, hiển thị menu tương tác
if (-not $ToVersion) {
    Write-Host "    Các version có sẵn:" -ForegroundColor Cyan

    $TagList = @($AllTags)
    for ($i = 0; $i -lt $TagList.Count; $i++) {
        $tag     = $TagList[$i]
        $verNum  = $tag -replace '^v', ''
        $isCurrent = if ($verNum -eq $CurrentVersion) { "  ← HIỆN TẠI" } else { "" }
        $color   = if ($verNum -eq $CurrentVersion) { "Yellow" } else { "White" }
        Write-Host ("    {0,2}. {1}{2}" -f ($i + 1), $tag, $isCurrent) -ForegroundColor $color
    }

    Write-Host ""
    do {
        $choice = Read-Host "    Chọn số thứ tự version muốn quay về"
        $idx    = [int]$choice - 1
    } while ($idx -lt 0 -or $idx -ge $TagList.Count)

    $ToVersion = $TagList[$idx] -replace '^v', ''
}

# Chuẩn hoá: bỏ chữ 'v' nếu có
$ToVersion = $ToVersion -replace '^v', ''
$ToTag     = "v$ToVersion"

# Kiểm tra tag tồn tại
if ($AllTags -notcontains $ToTag) {
    Write-Fail "Tag $ToTag không tồn tại trong repo."
    Write-Info "Các tag có sẵn: $($AllTags -join ', ')"
    exit 1
}

if ($ToVersion -eq $CurrentVersion) {
    Write-Warn "Bạn đang ở version $CurrentVersion rồi — không cần rollback?"
    $confirm = Read-Host "    Vẫn tiếp tục? (y/N)"
    if ($confirm -notin @('y','Y')) { Write-Host "`nĐã huỷ."; exit 0 }
}

Write-Info "Version hiện tại : $CurrentVersion"
Write-Info "Rollback về      : $ToVersion"

# ─── Xác nhận ─────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "    ╔═══════════════════════════════════════════════╗" -ForegroundColor Red
Write-Host "    ║  ⚠  CẢNH BÁO: Sắp rollback về v$ToVersion   " -ForegroundColor Red
Write-Host "    ║  Toàn bộ code sẽ trở về trạng thái $ToTag    " -ForegroundColor Red
if ($RestoreDB) {
Write-Host "    ║  + Database sẽ bị khôi phục từ backup!        " -ForegroundColor Red
}
Write-Host "    ╚═══════════════════════════════════════════════╝" -ForegroundColor Red
Write-Host ""

$confirm = Read-Host "    Xác nhận rollback về v${ToVersion}? (yes/N)"
if ($confirm -ne 'yes') {
    Write-Host "`nĐã huỷ rollback."
    exit 0
}

# ─── Bước 1: Backup DB hiện tại (an toàn) ────────────────────────────────────
Write-Step "1/6" "Backup database hiện tại (an toàn)"

if ($NoDB) {
    Write-Warn "Bỏ qua backup DB hiện tại (--NoDB)"
} else {
    if (-not $DryRun) { New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null }

    $SafeBackup = Join-Path $BackupDir "pre_rollback_from_v${CurrentVersion}_to_v${ToVersion}_${Timestamp}.sql"
    $DbRunning  = docker compose ps db --status running --quiet 2>$null

    if (-not $DbRunning) {
        Write-Warn "Container DB không chạy — bỏ qua backup tự động"
    } else {
        if (-not $DryRun) {
            docker compose exec -T db pg_dump -U sofa_user sofa_flow_dev | Set-Content -Path $SafeBackup -Encoding UTF8
            if (Test-Path $SafeBackup) {
                $Size = (Get-Item $SafeBackup).Length / 1KB
                Write-OK "Backup an toàn: $SafeBackup ($([math]::Round($Size,1)) KB)"
                Write-Info "→ Nếu rollback này có vấn đề, restore bằng file trên"
            } else {
                Write-Warn "Backup không tạo được — tiếp tục rollback với rủi ro mất data"
            }
        } else {
            Write-Info "[DryRun] docker compose exec -T db pg_dump ... > $SafeBackup"
        }
    }
}

# ─── Bước 2: Rollback code về version cũ ─────────────────────────────────────
Write-Step "2/6" "Khôi phục code về $ToTag"

Write-Info "Lấy files từ tag $ToTag..."
Invoke-Step "git fetch --tags"
Invoke-Step "git checkout $ToTag -- ."

Write-Info "Tạo commit rollback (để lịch sử git sạch)..."
$RollbackMsg = "rollback: restore code to v${ToVersion} (from v${CurrentVersion})"
Invoke-Step "git add -A"
if (-not $DryRun) {
    # Kiểm tra có thay đổi không
    $Changes = git diff --cached --name-only
    if ($Changes) {
        Invoke-Step "git commit -m `"$RollbackMsg`""
        Write-OK "Commit rollback tạo thành công"
    } else {
        Write-Warn "Không có thay đổi nào — version này giống với HEAD"
    }
} else {
    Write-Info "[DryRun] git commit -m '$RollbackMsg'"
}

# ─── Bước 3: Khôi phục database (tuỳ chọn) ───────────────────────────────────
Write-Step "3/6" "Khôi phục database"

if (-not $RestoreDB) {
    Write-Info "Bỏ qua khôi phục DB (dùng --RestoreDB để bật)"
    Write-Info "→ Database giữ nguyên trạng thái hiện tại (thường an toàn khi rollback)"
} else {
    Write-Warn "⚠  Khôi phục DB sẽ GHI ĐÈ toàn bộ dữ liệu hiện tại!"

    # Tìm các file backup liên quan đến version này
    $BackupFiles = @()
    if (Test-Path $BackupDir) {
        $BackupFiles = @(Get-ChildItem -Path $BackupDir -Filter "*.sql" |
                         Sort-Object LastWriteTime -Descending)
    }

    if (-not $BackupFiles) {
        Write-Warn "Không tìm thấy file backup nào trong $BackupDir"
        Write-Info "Bỏ qua khôi phục DB"
    } else {
        Write-Host "`n    Các file backup có sẵn:" -ForegroundColor Cyan
        for ($i = 0; $i -lt [Math]::Min($BackupFiles.Count, 10); $i++) {
            $f    = $BackupFiles[$i]
            $size = [math]::Round($f.Length / 1KB, 1)
            Write-Host ("    {0,2}. {1}  ({2} KB,  {3})" -f `
                ($i+1), $f.Name, $size, $f.LastWriteTime.ToString("dd/MM/yyyy HH:mm")) -ForegroundColor White
        }
        Write-Host ""

        do {
            $dbChoice = Read-Host "    Chọn số thứ tự file backup muốn restore (0 = bỏ qua)"
            $dbIdx    = [int]$dbChoice
        } while ($dbIdx -lt 0 -or $dbIdx -gt $BackupFiles.Count)

        if ($dbIdx -eq 0) {
            Write-Warn "Bỏ qua khôi phục DB"
        } else {
            $RestoreFile = $BackupFiles[$dbIdx - 1].FullName
            Write-Info "Đang restore: $RestoreFile"

            $confirmDB = Read-Host "    Xác nhận GHI ĐÈ database bằng file này? (yes/N)"
            if ($confirmDB -eq 'yes') {
                if (-not $DryRun) {
                    # Drop + recreate + restore
                    docker compose exec -T db psql -U sofa_user -d postgres -c "DROP DATABASE IF EXISTS sofa_flow_dev;" 2>$null
                    docker compose exec -T db psql -U sofa_user -d postgres -c "CREATE DATABASE sofa_flow_dev;" 2>$null
                    Get-Content $RestoreFile -Raw | docker compose exec -T db psql -U sofa_user -d sofa_flow_dev
                    Write-OK "Database đã được khôi phục từ $($BackupFiles[$dbIdx-1].Name)"
                } else {
                    Write-Info "[DryRun] DROP/CREATE/RESTORE database từ $RestoreFile"
                }
            } else {
                Write-Warn "Bỏ qua khôi phục DB"
            }
        }
    }
}

# ─── Bước 4: Docker rebuild ───────────────────────────────────────────────────
Write-Step "4/6" "Docker rebuild"

if ($NoDocker) {
    Write-Warn "Bỏ qua Docker rebuild (--NoDocker)"
} else {
    Write-Info "Build lại image với code của v$ToVersion..."
    Invoke-Step "docker compose up --build -d"
    if (-not $DryRun) { Start-Sleep -Seconds 5 }
    Write-OK "Docker containers đã restart với code v$ToVersion"
}

# ─── Bước 5: Health check ─────────────────────────────────────────────────────
Write-Step "5/6" "Health check"

if ($NoDocker) {
    Write-Warn "Bỏ qua health check"
} else {
    try {
        if (-not $DryRun) {
            $Response = Invoke-WebRequest -Uri "http://localhost:5000/auth/login" `
                            -MaximumRedirection 5 -UseBasicParsing -TimeoutSec 10
            if ($Response.StatusCode -eq 200) {
                Write-OK "Health check OK — HTTP $($Response.StatusCode)"
            } else {
                Write-Warn "HTTP $($Response.StatusCode) — kiểm tra logs"
            }
        } else {
            Write-Info "[DryRun] GET http://localhost:5000/auth/login"
        }
    } catch {
        Write-Warn "Health check thất bại: $_"
        Write-Warn "Xem logs: docker compose logs app --tail=30"
    }
}

# ─── Bước 6: Thông báo kết quả ───────────────────────────────────────────────
Write-Step "6/6" "Hoàn tất"

Write-Host "`n$Line" -ForegroundColor Green
Write-Host "   ✅  Rollback về v$ToVersion hoàn tất!" -ForegroundColor Green
Write-Host "$Line" -ForegroundColor Green
Write-Host ""
Write-Host " Đã rollback : v$CurrentVersion → v$ToVersion" -ForegroundColor White
if (-not $NoDB) {
    Write-Host " DB Backup   : $SafeBackup" -ForegroundColor White
    Write-Host "               (giữ lại để undo rollback nếu cần)" -ForegroundColor Gray
}
Write-Host " App URL     : http://localhost:5000" -ForegroundColor White
Write-Host ""
Write-Host " Để undo rollback này và quay lại v${CurrentVersion}:" -ForegroundColor Gray
Write-Host "   git revert HEAD --no-edit ; docker compose up --build -d" -ForegroundColor Gray
Write-Host ""
