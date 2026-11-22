param([string]$ZigPath)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$testArgs = @((Join-Path $PSScriptRoot 'test.py'))
if ($ZigPath) { $testArgs += @('--zig', $ZigPath) }
else {
    $zigCommand = Get-Command zig -ErrorAction SilentlyContinue
    if ($zigCommand) { $testArgs += @('--zig', $zigCommand.Source) }
    else { throw 'Install Zig or pass -ZigPath. Python-only checks: python tools/test.py' }
}
Push-Location $repo
try {
    & python @testArgs
    if ($LASTEXITCODE -ne 0) { throw 'Radio lab checks failed; see .build/test-results.json' }
}
finally { Pop-Location }
