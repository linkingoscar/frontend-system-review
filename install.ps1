<#
.SYNOPSIS
    将 frontend-system-review skill 安装到各 AI 平台的 skills 目录。

.DESCRIPTION
    支持 Codex / Claude Code / OpenCode / Gemini CLI / Cline / Cursor / Copilot / 通用 .agents。
    兼容 PowerShell 5.1+(推荐 pwsh 7)。默认复制模式,不建符号链接(避免 Windows 权限问题)。

.PARAMETER Platform
    逗号分隔的平台列表:generic,codex,claude,opencode,gemini,cline,cursor,copilot(默认全部)。

.PARAMETER Scope
    user(安装到当前用户目录,默认)或 project(安装到项目目录)。

.PARAMETER ProjectDir
    与 -Scope project 配合使用的项目目录(默认当前目录)。

.PARAMETER DryRun
    只显示将执行的操作,不复制。

.PARAMETER Force
    目标已存在时先删除再安装。

.PARAMETER Help
    显示帮助。

.EXAMPLE
    .\install.ps1
    .\install.ps1 -Platform generic,claude,opencode
    .\install.ps1 -Scope project -ProjectDir D:\my-project -Force
    .\install.ps1 -DryRun
#>

[CmdletBinding()]
param(
    [string]$Platform = "generic,codex,claude,opencode,gemini,cline,cursor,copilot",
    [ValidateSet("user", "project")]
    [string]$Scope = "user",
    [string]$ProjectDir = "",
    [switch]$DryRun,
    [switch]$Force,
    [switch]$Help
)

$ErrorActionPreference = "Stop"
$SkillName = "frontend-system-review"
$SourceDir = $PSScriptRoot

$ValidPlatforms = @("generic", "codex", "claude", "opencode", "gemini", "cline", "cursor", "copilot")

if ($Help) {
    Get-Help $MyInvocation.MyCommand.Path
    exit 0
}

# --- 解析并校验平台列表 ---
$Platforms = @()
foreach ($p in ($Platform -split ",")) {
    $p = $p.Trim()
    if ($p -ne "" -and $ValidPlatforms -notcontains $p) {
        Write-Error "unknown platform '$p' (valid: $($ValidPlatforms -join ', '))"
        exit 2
    }
    if ($p -ne "") { $Platforms += $p }
}
if ($Platforms.Count -eq 0) { $Platforms = $ValidPlatforms }

# --- 平台目录映射 ---
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
$ProjectBase = (Get-Location).Path
if ($ProjectDir -ne "") { $ProjectBase = $ProjectDir }

function Get-PlatformDir([string]$p) {
    if ($Scope -eq "project") {
        switch ($p) {
            "generic"  { return Join-Path $ProjectBase ".agents\skills" }
            "codex"    { return Join-Path $ProjectBase ".codex\skills" }
            "claude"   { return Join-Path $ProjectBase ".claude\skills" }
            "opencode" { return Join-Path $ProjectBase ".opencode\skills" }
            "gemini"   { return Join-Path $ProjectBase ".gemini\skills" }
            "cline"    { return Join-Path $ProjectBase ".cline\skills" }
            "cursor"   { return Join-Path $ProjectBase ".cursor\skills" }
            "copilot"  { return Join-Path $ProjectBase ".copilot\skills" }
        }
    }
    return $UserDirs[$p]
}

# --- 执行安装 ---
$ok = 0; $skip = 0; $fail = 0

foreach ($p in $Platforms) {
    $base = Get-PlatformDir $p
    $dest = Join-Path $base $SkillName
    $display = $dest.Replace($HOME, "~")

    if (Test-Path -LiteralPath $dest) {
        if (-not $Force) {
            Write-Host "[skip] $p -> $display : already exists (use -Force)"
            $skip++
            continue
        }
        if ($DryRun) {
            Write-Host "[dry-run] $p -> $display (would remove existing, then install)"
            $ok++
            continue
        }
        Remove-Item -LiteralPath $dest -Recurse -Force
    }

    if ($DryRun) {
        Write-Host "[dry-run] $p -> $display"
        $ok++
        continue
    }

    try {
        New-Item -ItemType Directory -Force -Path $base | Out-Null
        Copy-Item -LiteralPath $SourceDir -Destination $dest -Recurse -Force
        # 排除 .git 与安装脚本自身
        foreach ($exclude in @(".git", "install.sh", "install.ps1")) {
            $target = Join-Path $dest $exclude
            if (Test-Path -LiteralPath $target) {
                Remove-Item -LiteralPath $target -Recurse -Force
            }
        }
        Write-Host "[ok] $p -> $display"
        $ok++
    }
    catch {
        Write-Host "[fail] $p -> $display : $($_.Exception.Message)" -ForegroundColor Red
        $fail++
    }
}

Write-Host ""
Write-Host "Summary: $ok installed, $skip skipped, $fail failed"
if ($DryRun) { Write-Host "Dry run only - nothing was copied." }
if ($fail -gt 0) { exit 1 }
if (-not $DryRun -and $ok -gt 0) {
    Write-Host "Verify: run /skills inside the target tool's session."
}
exit 0
