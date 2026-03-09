#!/usr/bin/env pwsh
<#
.SYNOPSIS
    SofaFlow release helper — bumps version, updates CHANGELOG, creates git tag.

.DESCRIPTION
    Usage:
        .\scripts\release.ps1 -Bump patch      # 1.0.0 → 1.0.1  (bug fix)
        .\scripts\release.ps1 -Bump minor      # 1.0.1 → 1.1.0  (new feature)
        .\scripts\release.ps1 -Bump major      # 1.1.0 → 2.0.0  (breaking change)
        .\scripts\release.ps1 -Bump patch -DryRun   # preview only, no changes

.NOTES
    - Phải chạy từ thư mục gốc của project
    - Phải có git đã cấu hình
    - Sau khi chạy xong: cập nhật phần [Unreleased] trong CHANGELOG.md rồi push
#>

param(
    [Parameter(Mandatory)]
    [ValidateSet('major', 'minor', 'patch')]
    [string]$Bump,

    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# ── 1. Read current version ─────────────────────────────────────────
$versionFile = Join-Path $PSScriptRoot '..\VERSION'
$current = (Get-Content $versionFile -Raw).Trim()
$parts = $current -split '\.' | ForEach-Object { [int]$_ }

# ── 2. Bump ──────────────────────────────────────────────────────────
switch ($Bump) {
    'major' { $parts = @($parts[0] + 1, 0, 0) }
    'minor' { $parts = @($parts[0], $parts[1] + 1, 0) }
    'patch' { $parts = @($parts[0], $parts[1], $parts[2] + 1) }
}
$next = "$($parts[0]).$($parts[1]).$($parts[2])"
$tag  = "v$next"
$date = Get-Date -Format 'yyyy-MM-dd'

Write-Host ""
Write-Host "  Current version : $current"
Write-Host "  New version     : $next  ($tag)"
Write-Host "  Date            : $date"
if ($DryRun) {
    Write-Host "  [DRY RUN] — no files changed, no git commands executed." -ForegroundColor Yellow
    Write-Host ""
    exit 0
}

# ── 3. Write VERSION ─────────────────────────────────────────────────
Set-Content $versionFile "$next`n" -NoNewline
Write-Host "`n  ✔ VERSION updated" -ForegroundColor Green

# ── 4. Update CHANGELOG.md — move [Unreleased] to new version ────────
$clPath = Join-Path $PSScriptRoot '..\CHANGELOG.md'
$cl = Get-Content $clPath -Raw

# Replace the [Unreleased] heading block with a versioned section
$cl = $cl -replace (
    '## \[Unreleased\]\s*\n(---\s*\n)?' ),
    "## [Unreleased]`n`n---`n`n## [$next] - $date`n`n### Changed`n- *(dán các thay đổi vào đây)*`n`n"

# Update comparison links at the bottom
$repoUrl = 'https://github.com/tranquanguit/sofa-flow'
$prevTag  = "v$current"
$cl = $cl -replace "\[Unreleased\]: .*", "[Unreleased]: $repoUrl/compare/$tag...HEAD"
# Insert new version link after [Unreleased] link
$cl = $cl -replace "(\[Unreleased\]:.*\n)", "`$1[$next]: $repoUrl/compare/$prevTag...$tag`n"

Set-Content $clPath $cl -NoNewline
Write-Host "  ✔ CHANGELOG.md updated" -ForegroundColor Green

# ── 5. Git commit + tag ──────────────────────────────────────────────
git add VERSION CHANGELOG.md
git commit -m "chore: release $tag"
git tag -a $tag -m "Release $tag"

Write-Host "  ✔ Git commit + tag $tag created" -ForegroundColor Green
Write-Host ""
Write-Host "  Next steps:" -ForegroundColor Cyan
Write-Host "    1. Mở CHANGELOG.md, điền nội dung vào phần [$next]"
Write-Host "    2. git add CHANGELOG.md && git commit --amend --no-edit"
Write-Host "    3. git push origin main --tags"
Write-Host ""
