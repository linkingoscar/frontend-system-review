<#
.SYNOPSIS
    安装 Frontend System Review suite。

.DESCRIPTION
    从仓库 skills/ 规范源安装总控和六个专项 skill。默认安装全部 skill 到通用用户目录。

.PARAMETER Platform
    逗号分隔的平台:generic,codex,claude,opencode,gemini,cline,cursor,copilot,all(默认 generic)。

.PARAMETER Skill
    逗号分隔的 skill 名称或 all(默认 all)。

.PARAMETER Scope
    user(默认)或 project。

.EXAMPLE
    .\install.ps1
    .\install.ps1 -Skill frontend-system-review -Platform codex
    .\install.ps1 -Platform all -Force
#>

[CmdletBinding()]
param(
    [string]$Platform = "generic",
    [string]$Skill = "all",
    [ValidateSet("user", "project")]
    [string]$Scope = "user",
    [string]$ProjectDir = "",
    [switch]$DryRun,
    [switch]$Force,
    [switch]$Help
)

$ErrorActionPreference = "Stop"
$SourceRoot = Join-Path $PSScriptRoot "skills"
$ValidPlatforms = @("generic", "codex", "claude", "opencode", "gemini", "cline", "cursor", "copilot")
$AvailableSkills = @(Get-ChildItem -LiteralPath $SourceRoot -Directory | Where-Object {
    Test-Path -LiteralPath (Join-Path $_.FullName "SKILL.md") -PathType Leaf
} | Sort-Object Name | Select-Object -ExpandProperty Name)

if ($Help) { Get-Help $MyInvocation.MyCommand.Path; exit 0 }
if ($AvailableSkills.Count -eq 0) { Write-Error "no canonical skills found below $SourceRoot"; exit 1 }

$Platforms = @()
foreach ($item in ($Platform -split ",")) {
    $item = $item.Trim()
    if ($item -eq "all") { $Platforms += $ValidPlatforms; continue }
    if ($item -and $ValidPlatforms -notcontains $item) { Write-Error "unknown platform '$item'"; exit 2 }
    if ($item) { $Platforms += $item }
}
if ($Platforms.Count -eq 0) { Write-Error "at least one platform is required"; exit 2 }
$Platforms = @($Platforms | Select-Object -Unique)

$Skills = @()
foreach ($item in ($Skill -split ",")) {
    $item = $item.Trim()
    if ($item -eq "all") { $Skills += $AvailableSkills; continue }
    if ($item -and $AvailableSkills -notcontains $item) { Write-Error "unknown skill '$item' (available: $($AvailableSkills -join ', '))"; exit 2 }
    if ($item) { $Skills += $item }
}
if ($Skills.Count -eq 0) { Write-Error "at least one skill is required"; exit 2 }
$Skills = @($Skills | Select-Object -Unique)

$UserDirs = @{
    generic  = Join-Path $HOME ".agents\skills"
    codex    = Join-Path $HOME ".codex\skills"
    claude   = Join-Path $HOME ".claude\skills"
    opencode = Join-Path $HOME ".config\opencode\skills"
    gemini   = Join-Path $HOME ".gemini\skills"
    cline    = Join-Path $HOME ".cline\skills"
    cursor   = Join-Path $HOME ".cursor\skills"
    copilot  = Join-Path $HOME ".copilot\skills"
}
$ProjectBase = if ($ProjectDir) { $ProjectDir } else { (Get-Location).Path }

function Get-PlatformDir([string]$name) {
    if ($Scope -eq "user") { return $UserDirs[$name] }
    $suffix = switch ($name) {
        "generic" { ".agents\skills" }
        "codex" { ".codex\skills" }
        "claude" { ".claude\skills" }
        "opencode" { ".opencode\skills" }
        "gemini" { ".gemini\skills" }
        "cline" { ".cline\skills" }
        "cursor" { ".cursor\skills" }
        "copilot" { ".copilot\skills" }
    }
    return Join-Path $ProjectBase $suffix
}

function Get-FileMap([string]$root) {
    $map = @{}
    $rootPrefix = [IO.Path]::GetFullPath($root).TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
    Get-ChildItem -LiteralPath $root -File -Recurse | Where-Object {
        $_.FullName -notmatch '[\\/]__pycache__[\\/]' -and $_.Extension -ne '.pyc' -and $_.Name -ne '.DS_Store'
    } | ForEach-Object {
        $relative = $_.FullName.Substring($rootPrefix.Length).Replace('\', '/')
        $map[$relative] = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
    }
    return $map
}

function Test-InstallParity([string]$source, [string]$destination) {
    $sourceMap = Get-FileMap $source
    $destinationMap = Get-FileMap $destination
    if ($sourceMap.Count -ne $destinationMap.Count) { return $false }
    foreach ($relative in $sourceMap.Keys) {
        if (-not $destinationMap.ContainsKey($relative) -or $destinationMap[$relative] -ne $sourceMap[$relative]) { return $false }
    }
    return $true
}

$ok = 0; $skip = 0; $fail = 0
foreach ($platformName in $Platforms) {
    $base = Get-PlatformDir $platformName
    foreach ($skillName in $Skills) {
        $source = Join-Path $SourceRoot $skillName
        $dest = Join-Path $base $skillName
        $resolvedBase = [IO.Path]::GetFullPath($base).TrimEnd('\', '/')
        $resolvedDest = [IO.Path]::GetFullPath($dest)
        if ([IO.Path]::GetDirectoryName($resolvedDest).TrimEnd('\', '/') -ne $resolvedBase) {
            Write-Host "[fail] unsafe target: $resolvedDest" -ForegroundColor Red; $fail++; continue
        }
        $display = $dest.Replace($HOME, "~")
        if (Test-Path -LiteralPath $dest) {
            if (-not $Force) { Write-Host "[skip] $platformName/$skillName -> $display (use -Force)"; $skip++; continue }
            if (-not $DryRun) { Remove-Item -LiteralPath $dest -Recurse -Force }
        }
        if ($DryRun) { Write-Host "[dry-run] $platformName/$skillName -> $display"; $ok++; continue }
        try {
            New-Item -ItemType Directory -Force -Path $base | Out-Null
            Copy-Item -LiteralPath $source -Destination $dest -Recurse -Force
            if (-not (Test-InstallParity $source $dest)) { throw "post-install SHA-256 verification failed" }
            Write-Host "[ok] $platformName/$skillName -> $display"; $ok++
        } catch {
            Write-Host "[fail] $platformName/$skillName -> $display : $($_.Exception.Message)" -ForegroundColor Red; $fail++
        }
    }
}

Write-Host ""
Write-Host "Summary: $ok installed, $skip skipped, $fail failed"
if ($DryRun) { Write-Host "Dry run only - nothing was copied." }
if ($fail -gt 0) { exit 1 }
exit 0
