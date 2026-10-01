$ErrorActionPreference = "Stop"
if (-not $env:PGPASSWORD) {
    throw "Set the PGPASSWORD environment variable before running this script (see .env.example)."
}
$BackupDir = $PSScriptRoot
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupFile = "$BackupDir/afilearn_analytics_$Timestamp.dump"

New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null

Write-Host "Starting backup: $BackupFile"
pg_dump -h localhost -U afilearn_admin -d afilearn_analytics -F c -f $BackupFile
$sizeKB = [math]::Round((Get-Item $BackupFile).Length / 1KB, 1)
Write-Host "Backup complete: $sizeKB KB"

$backups = Get-ChildItem "$BackupDir/afilearn_analytics_*.dump" | Sort-Object LastWriteTime -Descending
if ($backups.Count -gt 7) {
    $backups | Select-Object -Skip 7 | Remove-Item
}
$remaining = (Get-ChildItem "$BackupDir/afilearn_analytics_*.dump").Count
Write-Host "Retention applied: $remaining backups retained"

Write-Host ""
Write-Host "To restore into a fresh database:"
Write-Host "  createdb -h localhost -U afilearn_admin afilearn_analytics_restored"
Write-Host "  pg_restore -h localhost -U afilearn_admin -d afilearn_analytics_restored $BackupFile"