# PowerShell launcher for ai-job-search
# Configures local directories within PROJECT_ROOT/.local to prevent global pollution
# Strictly propagates Python exit codes to caller

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

# Configure local caches and temp within PROJECT_ROOT/.local
$LocalDir = Join-Path $ProjectRoot ".local"
$TempDir = Join-Path $LocalDir "temp"
$CacheDir = Join-Path $LocalDir "cache"

if (-not (Test-Path $TempDir)) { New-Item -ItemType Directory -Force -Path $TempDir | Out-Null }
if (-not (Test-Path $CacheDir)) { New-Item -ItemType Directory -Force -Path $CacheDir | Out-Null }

$env:TEMP = $TempDir
$env:TMP = $TempDir
$env:PYTHONPYCACHEPREFIX = $CacheDir

$SubCommand = $args[0]

if (-not $SubCommand) {
    Write-Host "ai-job-search Windows Launcher" -ForegroundColor Cyan
    Write-Host "Cú pháp:"
    Write-Host "  .\run.ps1 test                       : Chạy bộ kiểm thử tự động toàn diện"
    Write-Host "  .\run.ps1 eval --file <path> [...]  : Đánh giá mô tả công việc (JD)"
    Write-Host "  .\run.ps1 tracker list               : Xem danh sách theo dõi ứng tuyển"
    Write-Host "  .\run.ps1 tracker export             : Xuất dữ liệu tracker ra CSV"
    Write-Host "  .\run.ps1 dedup --file <path>        : Lọc trùng danh sách JD"
    exit 0
}

if ($SubCommand -eq "test") {
    python -m unittest tests.test_all
    exit $LASTEXITCODE
} elseif ($SubCommand -eq "eval") {
    $Remaining = $args[1..($args.Length-1)]
    $hasTrackerFile = ($Remaining -contains "--tracker-file")
    $isFixture = ($Remaining -match "fixtures" -or $Remaining -match "tests[/\\]" -or $Remaining -match "live_jds")
    if ($isFixture -and -not $hasTrackerFile) {
        $Remaining += @("--tracker-file", ".local/temp/demo_tracker.json")
    }
    python -m src.cli evaluate $Remaining
    exit $LASTEXITCODE
} elseif ($SubCommand -eq "tracker") {
    $Remaining = $args[1..($args.Length-1)]
    python -m src.cli tracker $Remaining
    exit $LASTEXITCODE
} elseif ($SubCommand -eq "dedup") {
    $Remaining = $args[1..($args.Length-1)]
    python -m src.cli deduplicate $Remaining
    exit $LASTEXITCODE
} else {
    python -m src.cli $args
    exit $LASTEXITCODE
}
