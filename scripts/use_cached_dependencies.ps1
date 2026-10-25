# Offline development bootstrap: copy readable, already unpacked Python packages.
# Does not modify the shared cache or access the network.
param([string[]]$Packages)
$ErrorActionPreference = 'Stop'
$archiveRoot = Join-Path $env:LOCALAPPDATA 'uv/cache/archive-v0'
$sitePackages = Join-Path $PSScriptRoot '../.venv/Lib/site-packages'
$wanted = @('sqlalchemy', 'alembic', 'greenlet', 'mako', 'markupsafe',
    'typing_extensions', 'pytest', 'pytest_asyncio', 'ruff', 'tzdata',
    'packaging', 'pluggy', 'iniconfig', 'pygments', 'colorama')
if ($Packages) { $wanted = $Packages }
$chosen = @{}
foreach ($directory in Get-ChildItem -LiteralPath $archiveRoot -Directory) {
    foreach ($info in Get-ChildItem -LiteralPath $directory.FullName -Directory -Filter '*.dist-info') {
        $package = ($info.Name -split '-')[0].ToLowerInvariant()
        if ($package -notin $wanted) { continue }
        $version = (($info.Name -replace '\.dist-info$', '') -split '-')[1]
        $parsedVersion = $null
        if (-not [version]::TryParse($version, [ref]$parsedVersion)) { continue }
        if ($package -eq 'sqlalchemy' -and $version -notlike '2.0.*') { continue }
        if (-not $chosen.ContainsKey($package) -or $parsedVersion -gt $chosen[$package].Version) {
            $chosen[$package] = @{ Path = $directory.FullName; Version = $parsedVersion }
        }
    }
}
foreach ($package in $wanted) {
    if (-not $chosen.ContainsKey($package)) { throw "Missing cached dependency: $package" }
    Write-Output "Installing cached $package $($chosen[$package].Version) from $($chosen[$package].Path)"
    Get-ChildItem -LiteralPath $chosen[$package].Path -Force |
        Copy-Item -Destination $sitePackages -Recurse -Force
}
