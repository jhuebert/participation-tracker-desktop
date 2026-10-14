param([switch]$Onedir)
$ErrorActionPreference = "Stop"
python -m pip install -r requirements-dev.txt
if ($Onedir) { $env:PT_ONEDIR = "1" }
else { Remove-Item Env:PT_ONEDIR -ErrorAction SilentlyContinue }
python -m PyInstaller --noconfirm --clean --distpath dist --workpath build ParticipationTracker.spec
if ($Onedir) { Write-Host "Built -> dist\Participation Tracker\Participation Tracker.exe" }
else { Write-Host "Built -> dist\Participation Tracker.exe" }
