<#
.SYNOPSIS
    SofaFlow — Deploy pipeline tự động
    Backup DB → Cập nhật version → Git commit + tag → Push → Docker rebuild → Health check

.PARAMETER Version
    Version mới muốn deploy, định dạng x.y.z  (bắt buộc)
    Ví dụ: 1.2.0

.PARAMETER Message
    Mô tả ngắn về nội dung release (tuỳ chọn)
    Nếu để trống sẽ được hỏi tương tác

.PARAMETER NoDB
    Bỏ qua bước backup database (dùng khi DB chưa chạy)

.PARAMETER NoPush
    Không push lên GitHub (chỉ commit local)

.PARAMETER NoDocker
    Không rebuild Docker sau deploy

.PARAMETER DryRun
    Chạy thử — in ra tất cả các bước nhưng KHÔNG thực sự thay đổi gì

.EXAMPLE
    .\scripts\deploy.ps1 -Version "1.2.0"
    .\scripts\deploy.ps1 -Version "1.2.0" -Message "Thêm tính năng quản lý NVL"
    .\scripts\deploy.ps1 -Version "1.2.0" -NoPush -NoDocker    # chỉ commit local
    .\scripts\deploy.ps1 -Version "1.2.0" -DryRun              # xem trước không làm gì
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory=$true, HelpMessage="Version mới, định dạng x.y.z (VD: 1.2.0)")]
    [ValidatePattern('^\d+\.\d+\.\d+$')]
    [string]$Version,

    [string]$Message = "",

    [switch]$NoDB,
    [switch]$NoPush,
    [switch]$NoDocker,
    [switch]$DryRun
)

# ─── Màu sắc / helper ──────────────────────────────────────────────────────────
function Write-Step  { param($n,$t) Write-Host "`n[$n] $t" -ForegroundColor Cyan }
function Write-OK    { param($t)    Write-Host "    ✔  $t" -ForegroundColor Green }
function Write-Warn  { param($t)    Write-Host "    ⚠  $t" -ForegroundColor Yellow }
function Write-Fail  { param($t)    Write-Host "    ✖  $t" -ForegroundColor Red }
function Write-Info  { param($t)    Write-Host "    •  $t" -ForegroundColor Gray }

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
Write-Host "`n$Line" -ForegroundColor Magenta
Write-Host "   🚀  SofaFlow Deploy Pipeline — v$Version" -ForegroundColor Magenta
if ($DryRun) { Write-Host "   [DRY RUN — không có thay đổi thực sự]" -ForegroundColor Yellow }
Write-Host "$Line`n" -ForegroundColor Magenta

$ProjectRoot = Split-Path $PSScriptRoot -Parent
Set-Location $ProjectRoot

$Timestamp   = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupDir   = Join-Path $ProjectRoot "backups"
$BackupFile  = Join-Path $BackupDir "before_v${Version}_${Timestamp}.sql"
$VersionFile = Join-Path $ProjectRoot "VERSION"
$ChangelogFile = Join-Path $ProjectRoot "CHANGELOG.md"

# ─── Bước 0: Kiểm tra version hiện tại ───────────────────────────────────────
Write-Step "0/7" "Kiểm tra trạng thái"

$CurrentVersion = (Get-Content $VersionFile -Encoding UTF8).Trim()
Write-Info "Version hiện tại : $CurrentVersion"
Write-Info "Version mới      : $Version"

if ($CurrentVersion -eq $Version) {
    Write-Warn "Version $Version đã là version hiện tại!"
    $confirm = Read-Host "    Tiếp tục không? (y/N)"
    if ($confirm -notin @('y','Y')) { Write-Host "`nĐã huỷ."; exit 0 }
}

# ─── Bước 0b: Kiểm tra git status ────────────────────────────────────────────
$GitStatus = git status --porcelain
if ($GitStatus) {
    Write-Warn "Có file chưa commit:"
    $GitStatus | ForEach-Object { Write-Info $_ }
    Write-Warn "Khuyến nghị: commit hoặc stash trước khi deploy."
    $confirm = Read-Host "    Vẫn tiếp tục? (y/N)"
    if ($confirm -notin @('y','Y')) { Write-Host "`nĐã huỷ."; exit 0 }
} else {
    Write-OK "Git working tree sạch"
}

# ─── Bước 1: Backup database ─────────────────────────────────────────────────
Write-Step "1/7" "Backup database"

if ($NoDB) {
    Write-Warn "Bỏ qua backup (--NoDB)"
} else {
    if (-not $DryRun) { New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null }
    Write-Info "Đang backup → $BackupFile"

    # Kiểm tra Docker container db có đang chạy không
    $DbRunning = docker compose ps db --status running --quiet 2>$null
    if (-not $DbRunning) {
        Write-Warn "Container DB không chạy — bỏ qua backup tự động"
        Write-Warn "Nếu dùng DB local, hãy backup thủ công trước khi tiếp tục!"
        $confirm = Read-Host "    Tiếp tục không? (y/N)"
        if ($confirm -notin @('y','Y')) { exit 0 }
    } else {
        if (-not $DryRun) {
            # pg_dump qua docker compose exec
            docker compose exec -T db pg_dump -U sofa_user sofa_flow_dev | Set-Content -Path $BackupFile -Encoding UTF8
            if (Test-Path $BackupFile) {
                $Size = (Get-Item $BackupFile).Length / 1KB
                Write-OK "Backup thành công ($([math]::Round($Size,1)) KB) → $BackupFile"
            } else {
                Write-Fail "Backup thất bại — file không được tạo"
                exit 1
            }
        } else {
            Write-Info "[DryRun] docker compose exec -T db pg_dump ... > $BackupFile"
        }
    }
}

# ─── Bước 2: Lấy release message ─────────────────────────────────────────────
Write-Step "2/7" "Nội dung release"

if (-not $Message) {
    Write-Host "    Nhập mô tả ngắn cho release này (Enter để dùng mặc định):" -ForegroundColor Cyan
    $Input = Read-Host "    Message"
    $Message = if ($Input.Trim()) { $Input.Trim() } else { "Release version $Version" }
}
Write-OK "Message: $Message"

# ─── Bước 3: Cập nhật VERSION ─────────────────────────────────────────────────
Write-Step "3/7" "Cập nhật VERSION và CHANGELOG"

if (-not $DryRun) {
    Set-Content -Path $VersionFile -Value $Version -Encoding UTF8 -NoNewline
    Write-OK "VERSION: $CurrentVersion → $Version"

    # Cập nhật CHANGELOG: đổi [Unreleased] thành [x.y.z] - ngày hôm nay
    $Today = Get-Date -Format "yyyy-MM-dd"
    $Content = Get-Content $ChangelogFile -Raw -Encoding UTF8

    # Thêm [x.y.z] - date header sau [Unreleased]
    $NewSection = "## [Unreleased]`n`n---`n`n## [$Version] - $Today`n`n### Added`n- $Message"
    $Content = $Content -replace '## \[Unreleased\]', $NewSection

    # Cập nhật comparison links ở cuối
    $Content = $Content -replace `
        "\[Unreleased\]: https://github.com/.+/compare/v.+\.\.\.HEAD", `
        "[Unreleased]: https://github.com/tranquanguit/sofa-flow/compare/v${Version}...HEAD"

    # Thêm link cho version mới (sau [Unreleased] link)
    if ($Content -notmatch "\[$Version\]:") {
        $Content = $Content -replace `
            "(\[Unreleased\]:.*)`n", `
            "`$1`n[$Version]: https://github.com/tranquanguit/sofa-flow/compare/v${CurrentVersion}...v${Version}`n"
    }

    Set-Content -Path $ChangelogFile -Value $Content -Encoding UTF8
    Write-OK "CHANGELOG.md cập nhật — phiên bản [$Version] - $Today"
    Write-Warn "Nếu muốn thêm chi tiết: mở CHANGELOG.md và điền vào section [$Version] rồi 'git commit --amend'"
} else {
    Write-Info "[DryRun] Set-Content VERSION '$Version'"
    Write-Info "[DryRun] Cập nhật CHANGELOG.md"
}

# ─── Bước 4: Git commit và tag ────────────────────────────────────────────────
Write-Step "4/7" "Git commit + tag"

Invoke-Step "git add -A"
Invoke-Step "git commit -m `"release: v${Version} — ${Message}`""
Invoke-Step "git tag v${Version}"
Write-OK "Đã commit và tạo tag v$Version"

# ─── Bước 5: Push lên GitHub ──────────────────────────────────────────────────
Write-Step "5/7" "Push lên GitHub"

if ($NoPush) {
    Write-Warn "Bỏ qua push (--NoPush) — tag và commit vẫn ở local"
} else {
    Invoke-Step "git push origin main --tags"
    Write-OK "Đã push main + tag v$Version lên GitHub"
}

# ─── Bước 6: Docker rebuild ───────────────────────────────────────────────────
Write-Step "6/7" "Docker rebuild"

if ($NoDocker) {
    Write-Warn "Bỏ qua Docker rebuild (--NoDocker)"
} else {
    Write-Info "Đang build lại image và restart containers..."
    Invoke-Step "docker compose up --build -d"
    # Đợi app sẵn sàng
    Write-Info "Chờ app khởi động..."
    if (-not $DryRun) { Start-Sleep -Seconds 5 }
    Write-OK "Docker containers đã restart"
}

# ─── Bước 7: Health check ─────────────────────────────────────────────────────
Write-Step "7/7" "Health check"

if ($NoDocker) {
    Write-Warn "Bỏ qua health check (--NoDocker)"
} else {
    try {
        if (-not $DryRun) {
            $Response = Invoke-WebRequest -Uri "http://localhost:5000/auth/login" `
                            -MaximumRedirection 5 -UseBasicParsing -TimeoutSec 10
            if ($Response.StatusCode -eq 200) {
                Write-OK "Health check OK — HTTP $($Response.StatusCode)"
            } else {
                Write-Warn "Health check trả về HTTP $($Response.StatusCode)"
            }
        } else {
            Write-Info "[DryRun] GET http://localhost:5000/auth/login"
        }
    } catch {
        Write-Warn "Health check thất bại: $_"
        Write-Warn "App có thể chưa khởi động xong — kiểm tra: docker compose logs app"
    }
}

# ─── Tổng kết ─────────────────────────────────────────────────────────────────
Write-Host "`n$Line" -ForegroundColor Green
Write-Host "   ✅  Deploy v$Version hoàn tất!" -ForegroundColor Green
Write-Host "$Line" -ForegroundColor Green
Write-Host ""
Write-Host " Version   : $CurrentVersion → $Version" -ForegroundColor White
if (-not $NoDB -and -not $DryRun) {
    Write-Host " DB Backup : $BackupFile" -ForegroundColor White
}
Write-Host " Tag       : v$Version (git tag)" -ForegroundColor White
if (-not $NoPush)    { Write-Host " GitHub    : https://github.com/tranquanguit/sofa-flow/releases/tag/v$Version" -ForegroundColor White }
if (-not $NoDocker)  { Write-Host " App URL   : http://localhost:5000" -ForegroundColor White }
Write-Host ""
Write-Host " Để xem logs: docker compose logs app -f" -ForegroundColor Gray
Write-Host ""
