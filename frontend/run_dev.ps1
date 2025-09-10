Param(
  [switch]$SkipInstall
)

$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
Write-Host '== Frontend Dev Runner =='
if (-not $SkipInstall) {
  Write-Host 'Installing node modules (if needed)...'
  npm install --silent | Out-Null
}
Write-Host 'Starting Vite dev on http://localhost:5173 ...'
npm run dev
Pop-Location
