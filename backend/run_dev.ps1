Param(
  [switch]$SkipInstall
)

$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot

Write-Host '== Backend Dev Runner =='

# Create venv if missing
if (-not (Test-Path '.venv/Scripts/python.exe')) {
  Write-Host 'Creating virtual environment...'
  python -m venv .venv
}

# Install deps
if (-not $SkipInstall) {
  Write-Host 'Installing requirements (this may take a minute)...'
  .\.venv\Scripts\python.exe -m pip install --upgrade pip | Out-Null
  .\.venv\Scripts\python.exe -m pip install -r requirements.txt | Out-Null
}

# Ensure .env with OpenAI-compatible config
$envPath = Join-Path $PSScriptRoot '.env'
if (-not (Test-Path $envPath)) { Copy-Item '.env.example' $envPath -Force }

$envContent = Get-Content $envPath -ErrorAction SilentlyContinue
$envText = ($envContent -join "`n")

if ($envText -notmatch '(?m)^LLM_PROVIDER=') { $envContent += 'LLM_PROVIDER=openai' }
if ($envText -notmatch '(?m)^OPENAI_BASE_URL=') { $envContent += 'OPENAI_BASE_URL=https://api.openai.com/v1' }
if ($envText -notmatch '(?m)^OPENAI_MODEL=') { $envContent += 'OPENAI_MODEL=gpt-4o-mini' }

$hasKeyLine = $envText -match '(?m)^OPENAI_API_KEY='
$hasEmptyKey = $envText -match '(?m)^OPENAI_API_KEY=\s*$'
if (-not $hasKeyLine -or $hasEmptyKey) {
  Write-Host 'Enter your OpenAI-compatible API key (input hidden):'
  $sec = Read-Host -AsSecureString 'OPENAI_API_KEY'
  $bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
  $plain = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
  if ($plain) { $plain = $plain.Trim() }
  if ($plain -and $plain.Trim().Length -gt 0) {
    $envContent = $envContent | ForEach-Object { if ($_ -match '^OPENAI_API_KEY=') { "OPENAI_API_KEY=$plain" } else { $_ } }
    if ($envContent -notmatch '(?m)^OPENAI_API_KEY=') { $envContent += "OPENAI_API_KEY=$plain" }
    Set-Content -Path $envPath -Value $envContent -Encoding UTF8
  }
}

Write-Host 'Starting FastAPI on http://localhost:8000 ...'
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --env-file .env

Pop-Location
