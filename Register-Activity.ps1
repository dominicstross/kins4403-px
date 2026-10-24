<#
.SYNOPSIS
    Registers or updates an activity entry inside a target module's _content.json.
.DESCRIPTION
    1. Resolves module numbers (e.g., -Module "7.2") into proper zero-padded paths 
       ("content/ch07/7.2_content.json" and "content/ch07/activities/<filename>").
    2. Validates on-disk existence of the activity file and target JSON.
    3. Auto-creates a styled starter HTML template if -CreateIfMissing is supplied.
    4. Writes both 'file' and 'path' keys to ensure compatibility with viewer.html.
    5. Cleans up all temporary execution files automatically.
#>
param(
    # e.g., "7.1", "7.2", "10.3"
    [string]$Module,

    # Optional explicit override for target JSON path
    [string]$TargetModuleJson,

    # Provide either just the filename or the full relative path
    [string]$ActivityFileName,
    [string]$ActivityFilePath,

    [Parameter(Mandatory = $true)]
    [string]$ActivityTitle,

    [Parameter(Mandatory = $true)]
    [string]$ActivityDesc,

    [ValidateSet("sim", "lab", "case", "h5p")]
    [string]$ActivityType = "h5p",

    # Switch to auto-scaffold a clean HTML starter template if file is not found
    [switch]$CreateIfMissing
)

$ErrorActionPreference = "Stop"

# 1. Resolve TargetModuleJson from -Module if not explicitly supplied
if (-not $TargetModuleJson) {
    if (-not $Module) {
        Write-Error "[ABORT] You must specify either -Module (e.g. '7.2') or -TargetModuleJson."
        return
    }
    $parts = $Module.Trim().Split('.')
    $chNum = [int]$parts[0]
    $chPadded = $chNum.ToString("D2")
    $TargetModuleJson = "content/ch$chPadded/${Module}_content.json"
}

# 2. Resolve ActivityFilePath from ActivityFileName if supplied
if (-not $ActivityFilePath) {
    if ($ActivityFileName) {
        if ($Module) {
            $chNum = [int]($Module.Trim().Split('.')[0])
            $chPadded = $chNum.ToString("D2")
        } elseif ($TargetModuleJson -match "ch(\d+)") {
            $chPadded = $Matches[1]
        } else {
            $chPadded = "01"
        }
        $ActivityFilePath = "content/ch$chPadded/activities/$ActivityFileName"
    } else {
        Write-Error "[ABORT] You must specify either -ActivityFilePath or -ActivityFileName."
        return
    }
}

# Normalize path separators for web/JSON consistency
$TargetModuleJson = $TargetModuleJson.Replace('\', '/')
$ActivityFilePath = $ActivityFilePath.Replace('\', '/')

# 3. Check for existence or create starter HTML file if requested
if (-not (Test-Path -Path $ActivityFilePath -PathType Leaf)) {
    if ($CreateIfMissing) {
        $parentDir = [System.IO.Path]::GetDirectoryName($ActivityFilePath)
        if ($parentDir -and -not (Test-Path -Path $parentDir)) {
            New-Item -ItemType Directory -Path $parentDir -Force | Out-Null
        }

        $htmlTemplate = @"
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>$ActivityTitle</title>
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      margin: 0;
      padding: 2rem;
      background-color: #f8fafc;
      color: #1e293b;
      display: flex;
      flex-direction: column;
      align-items: center;
    }
    .container {
      max-width: 800px;
      width: 100%;
      background: #ffffff;
      padding: 2rem;
      border-radius: 8px;
      box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
    }
    h1 {
      margin-top: 0;
      color: #0f172a;
    }
    p.desc {
      color: #64748b;
      font-size: 1.1rem;
      line-height: 1.5;
    }
    .sandbox {
      margin-top: 2rem;
      padding: 3rem 1.5rem;
      border: 2px dashed #cbd5e1;
      border-radius: 6px;
      text-align: center;
      color: #94a3b8;
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>$ActivityTitle</h1>
    <p class="desc">$ActivityDesc</p>
    <div class="sandbox">
      Interactive component canvas / container goes here.
    </div>
  </div>
</body>
</html>
"@
        $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::WriteAllText($ActivityFilePath, $htmlTemplate, $utf8NoBom)
        Write-Host "[CREATED] Starter HTML template generated at: $ActivityFilePath" -ForegroundColor Cyan
    } else {
        Write-Error "[ABORT] Activity file not found on disk at: $ActivityFilePath. Pass -CreateIfMissing to auto-create it."
        return
    }
}

# 4. Verify target module JSON exists on disk
if (-not (Test-Path -Path $TargetModuleJson -PathType Leaf)) {
    Write-Error "[ABORT] Target JSON module not found on disk at: $TargetModuleJson"
    return
}

# 5. Embedded Python script to safely register JSON payload
$tempPyScript = [System.IO.Path]::Combine([System.IO.Path]::GetTempPath(), "register_activity_$([System.Guid]::NewGuid().ToString('N')).py")

$pythonCode = @"
# -*- coding: utf-8 -*-
import json
import os
import sys

target_json = r"$TargetModuleJson"
activity_file = r"$ActivityFilePath"
activity_title = r"$ActivityTitle"
activity_desc = r"$ActivityDesc"
activity_type = r"$ActivityType"

if not os.path.isfile(activity_file):
    print(f"[ERROR] Activity file not found: {activity_file}", file=sys.stderr)
    sys.exit(1)

if not os.path.isfile(target_json):
    print(f"[ERROR] Target JSON not found: {target_json}", file=sys.stderr)
    sys.exit(1)

try:
    with open(target_json, 'r', encoding='utf-8') as f:
        data = json.load(f)
except Exception as e:
    print(f"[ERROR] Failed to read JSON file: {e}", file=sys.stderr)
    sys.exit(1)

if not isinstance(data, dict):
    data = {}

if "activities" not in data or not isinstance(data["activities"], list):
    data["activities"] = []

# Populates both 'file' and 'path' to maintain dual-compatibility with viewer logic
new_entry = {
    "type": activity_type,
    "title": activity_title,
    "desc": activity_desc,
    "file": activity_file,
    "path": activity_file
}

updated = False
for idx, item in enumerate(data["activities"]):
    if isinstance(item, dict):
        existing_path = item.get("file") or item.get("path")
        if existing_path == activity_file:
            data["activities"][idx] = new_entry
            updated = True
            break

if not updated:
    data["activities"].append(new_entry)

try:
    with open(target_json, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write('\n')
    status = "Updated existing" if updated else "Appended new"
    print(f"[SUCCESS] {status} activity '{activity_title}' in {target_json}")
except Exception as e:
    print(f"[ERROR] Failed to save JSON file: {e}", file=sys.stderr)
    sys.exit(1)
"@

try {
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($tempPyScript, $pythonCode, $utf8NoBom)
    python $tempPyScript
}
finally {
    if (Test-Path $tempPyScript) {
        Remove-Item -Path $tempPyScript -Force -ErrorAction SilentlyContinue
    }
}