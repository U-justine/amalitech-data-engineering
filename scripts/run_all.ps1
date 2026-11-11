<#
.SYNOPSIS
    Runs the whole flight price pipeline in one go, checking each step.

.DESCRIPTION
    I got tired of typing the same commands every time, so this does it all:
    1. check Docker is running, .env is there and the csv is in data\
    2. docker compose up -d, then wait until everything is healthy
    3. check the DAG loaded without errors
    4. check the email login (can skip it)
    5. trigger the DAG with my own run id and wait until it's done
    6. show the results from Postgres
    7. open the KPI report (data\reports\kpi_report.html)

    If something goes wrong it stops there and says what to do.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\run_all.ps1
.EXAMPLE
    .\scripts\run_all.ps1 -SkipEmailCheck -NoOpen
#>
[CmdletBinding()]
param(
    [switch]$SkipEmailCheck,     # don't test the Gmail connection
    [switch]$SendTestEmail,      # also send a test email during the email check
    [switch]$NoOpen,             # don't open the KPI report at the end
    [switch]$Download,           # get the Kaggle data first if the csv is missing
    [int]$TimeoutMinutes = 15    # how long to wait for the run to finish
)

# has to be "Continue": with "Stop", Windows PowerShell 5.1 stopped the script on an Airflow
# deprecation warning (it's printed on stderr). I check $LASTEXITCODE instead.
$ErrorActionPreference = "Continue"
$env:PYTHONWARNINGS = "ignore"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$Dag = "flight_price_pipeline"
$Csv = Join-Path $Root "data\Flight_Price_Dataset_of_Bangladesh.csv"
$Report = Join-Path $Root "data\reports\kpi_report.html"
$script:step = 0

function Step($text)  { $script:step++; Write-Host ""; Write-Host "[$script:step] $text" -ForegroundColor Cyan }
function Ok($text)    { Write-Host "    [OK]   $text" -ForegroundColor Green }
function Info($text)  { Write-Host "    $text" -ForegroundColor Gray }
function Warn($text)  { Write-Host "    [WARN] $text" -ForegroundColor Yellow }
function Fail($text, $hint) {
    Write-Host "    [FAIL] $text" -ForegroundColor Red
    if ($hint) { Write-Host "           -> $hint" -ForegroundColor Yellow }
    Write-Host ""; Write-Host "Stopped. See docs\HOW_TO_RUN.md (Troubleshooting)." -ForegroundColor Red
    exit 1
}
function Airflow([string[]]$cmdArgs) {
    # run an airflow command in the scheduler container, only keep stdout
    $out = & docker compose exec -T -e PYTHONWARNINGS=ignore airflow-scheduler airflow @cmdArgs 2>$null
    return ($out -join "`n")
}
function JsonFrom([string]$text) {
    # sometimes there's a warning before the json, so start at the first [
    $i = $text.IndexOf("[")
    if ($i -lt 0) { return @() }
    try { return ($text.Substring($i) | ConvertFrom-Json) } catch { return @() }
}
function EnvValue($name, $default) {
    $line = Get-Content (Join-Path $Root ".env") | Where-Object { $_ -match "^\s*$name\s*=" } | Select-Object -First 1
    if ($line) { return ($line -split "=", 2)[1].Trim() } else { return $default }
}

Write-Host "Flight Price Pipeline - full run" -ForegroundColor White
Write-Host "Project: $Root"

# ---- 1. checks
Step "Checking Docker, .env and the dataset"
& docker version --format "{{.Server.Version}}" *> $null
if ($LASTEXITCODE -ne 0) { Fail "Docker is not running." "Start Docker Desktop, wait until it says 'running', then run this script again." }
Ok "Docker is running"

if (-not (Test-Path (Join-Path $Root ".env"))) {
    Fail ".env file not found." "Copy-Item .env.example .env  then fill in SMTP_PASSWORD (see docs\EMAIL_SETUP.md)."
}
Ok ".env found"

if (-not (Test-Path $Csv)) {
    if ($Download) {
        Info "Dataset missing - downloading from Kaggle ..."
        $py = Join-Path $Root ".venv\Scripts\python.exe"
        if (-not (Test-Path $py)) { $py = "python" }
        & $py (Join-Path $Root "scripts\download_data.py")
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path $Csv)) { Fail "Download failed." "See docs\KAGGLE_SETUP.md (Option 1: download in the browser)." }
    } else {
        Fail "Dataset not found: data\Flight_Price_Dataset_of_Bangladesh.csv" "Run again with -Download, or follow docs\KAGGLE_SETUP.md."
    }
}
$rows = (Get-Content $Csv | Measure-Object -Line).Lines - 1
Ok ("Dataset found ({0:N0} rows)" -f $rows)

# ---- 2. start everything
Step "Starting the stack (docker compose up -d)"
& docker compose up -d --remove-orphans
if ($LASTEXITCODE -ne 0) { Fail "docker compose up failed." "Run: docker compose logs airflow-init --tail 50" }

Info "Waiting for the services to be healthy (up to 3 minutes) ..."
$services = "airflow-db", "mysql-staging", "postgres-analytics", "airflow-apiserver", "airflow-scheduler"
$deadline = (Get-Date).AddMinutes(3)
do {
    $notReady = @()
    foreach ($s in $services) {
        $id = (& docker compose ps -q $s) | Select-Object -First 1
        $health = if ($id) { (& docker inspect -f "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}" $id) } else { "missing" }
        if ($health -ne "healthy") { $notReady += "$s=$health" }
    }
    if ($notReady.Count -eq 0) { break }
    Start-Sleep -Seconds 5
} while ((Get-Date) -lt $deadline)
if ($notReady.Count -gt 0) { Fail ("Not healthy: " + ($notReady -join ", ")) "Run: docker compose ps   and   docker compose logs <service> --tail 50" }
Ok "All services healthy (Airflow UI: http://localhost:8080)"

# ---- 3. DAG ok?
Step "Checking the DAG"
$deadline = (Get-Date).AddMinutes(2)
do {
    $dags = Airflow @("dags", "list", "-o", "json")
    if ($dags -match $Dag) { break }
    Start-Sleep -Seconds 5
} while ((Get-Date) -lt $deadline)
if ($dags -notmatch $Dag) { Fail "DAG '$Dag' not found." "Check the UI for a 'Broken DAG' message, or: docker compose logs airflow-dag-processor --tail 50" }
$errors = Airflow @("dags", "list-import-errors", "-o", "json")
if ((JsonFrom $errors).Count -gt 0) { Fail "The DAG has import errors." "Run: docker compose exec airflow-scheduler airflow dags list-import-errors" }
Ok "DAG '$Dag' loaded, no import errors"
& docker compose exec -T -e PYTHONWARNINGS=ignore airflow-scheduler airflow dags unpause $Dag *> $null

# ---- 4. email
if ($SkipEmailCheck) {
    Step "Email check skipped (-SkipEmailCheck)"
} else {
    Step "Checking the email connection"
    $emailArgs = @("compose", "exec", "-T", "-e", "PYTHONWARNINGS=ignore", "-w", "/opt/airflow/dags", "airflow-scheduler", "python", "-m", "flight_pipeline.check_email")
    if ($SendTestEmail) { $emailArgs += "--send" }
    $emailOut = & docker @emailArgs 2>&1
    if ($LASTEXITCODE -eq 0) { Ok "Email connection works (alerts will reach $(EnvValue 'ALERT_EMAIL_TO' 'your inbox'))" }
    else {
        Warn "Email check failed - the pipeline still runs, alerts go to data\alerts.log."
        $emailOut | Select-String "FAIL" | ForEach-Object { Info $_.Line.Trim() }
    }
}

# ---- 5. run the pipeline
Step "Running the pipeline"
$runId = "manual__run_all_" + (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH-mm-ss")
$null = Airflow @("dags", "trigger", $Dag, "--run-id", $runId)
Info "Triggered run: $runId"
Info "Watch it live: http://localhost:8080/dags/$Dag"

$deadline = (Get-Date).AddMinutes($TimeoutMinutes)
$state = "queued"; $last = ""
do {
    Start-Sleep -Seconds 10
    $run = JsonFrom (Airflow @("dags", "list-runs", $Dag, "-o", "json")) | Where-Object { $_.run_id -eq $runId } | Select-Object -First 1
    if ($run) { $state = $run.state }
    if ($state -ne $last) { Info ("{0:HH:mm:ss}  state: {1}" -f (Get-Date), $state); $last = $state }
} while ($state -in @("queued", "running") -and (Get-Date) -lt $deadline)

if ($state -ne "success") {
    $tasks = JsonFrom (Airflow @("tasks", "states-for-dag-run", $Dag, $runId, "-o", "json"))
    $bad = $tasks | Where-Object { $_.state -in @("failed", "upstream_failed", "up_for_retry") }
    foreach ($t in $bad) { Info ("  {0,-45} {1}" -f $t.task_id, $t.state) }
    if ($state -in @("queued", "running")) { Fail "The run did not finish within $TimeoutMinutes minutes (still $state)." "Check the Grid view; a task may be waiting to retry." }
    Fail "The run finished with state '$state'." "Open the red task in the Airflow UI -> Logs, and see docs\RUNBOOK.md section 4. A FAILED email was sent."
}
Ok "Run succeeded: $runId"

# ---- 6. results
Step "Results in PostgreSQL"
$pgUser = EnvValue "ANALYTICS_PG_USER" "analytics_user"
$pgDb = EnvValue "ANALYTICS_PG_DB" "flight_analytics"
function Psql($sql) { & docker compose exec -T postgres-analytics psql -U $pgUser -d $pgDb -c $sql 2>$null }
Psql "SELECT batch_id, rows_in_file, rows_valid, rows_rejected, rows_loaded, loaded_at FROM analytics.pipeline_run_log WHERE batch_id = '$runId';"
Info "Top 5 airlines by average fare:"
Psql "SELECT fare_rank, airline, avg_total_fare, booking_count FROM analytics.kpi_avg_fare_by_airline ORDER BY fare_rank LIMIT 5;"
Info "Peak vs non-peak:"
Psql "SELECT season_label, booking_count, avg_total_fare, pct_diff_vs_baseline FROM analytics.v_peak_vs_offpeak;"
Info "Top 5 routes:"
Psql "SELECT route_rank, route, booking_count, avg_total_fare FROM analytics.v_top_routes LIMIT 5;"

# ---- 7. report
Step "KPI report"
if (Test-Path $Report) {
    $age = (Get-Date) - (Get-Item $Report).LastWriteTime
    if ($age.TotalMinutes -gt 30) { Warn "kpi_report.html is $([int]$age.TotalMinutes) minutes old - was the report task skipped?" }
    Ok "Report: $Report  (updated $((Get-Item $Report).LastWriteTime))"
    if (-not $NoOpen) { Start-Process $Report }
} else {
    Warn "Report not found at data\reports\kpi_report.html (check task load.build_kpi_report in the UI)."
}

Write-Host ""
Write-Host "Done. Run $runId succeeded." -ForegroundColor Green
Write-Host "  Airflow UI : http://localhost:8080/dags/$Dag"
Write-Host "  KPI report : data\reports\kpi_report.html"
Write-Host "  Email      : look for '[Airflow] SUCCESS' in $(EnvValue 'ALERT_EMAIL_TO' 'your inbox')"
