# Stitch the 24 rendered shots into the 1-minute Sepang highlight.
# Run AFTER cine_render.py has finished.
#
# Requires ffmpeg on PATH:  winget install --id Gyan.FFmpeg -e
# Run from:                 c:\Users\spoop\OneDrive\Documents\Class\hackathon\F1

$ErrorActionPreference = 'Stop'

# Prefer ffmpeg on PATH; fall back to the winget install location, since a
# freshly installed winget package is not visible to already-open terminals
# until PATH is refreshed.
$ffmpeg = "ffmpeg"
$ffprobe = "ffprobe"
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    $fallback = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" `
        -Directory -Filter "Gyan.FFmpeg*" -ErrorAction SilentlyContinue |
        ForEach-Object { Get-ChildItem $_.FullName -Recurse -Filter "ffmpeg.exe" -ErrorAction SilentlyContinue } |
        Select-Object -First 1
    if ($fallback) {
        $ffmpeg = $fallback.FullName
        $ffprobe = Join-Path $fallback.Directory.FullName "ffprobe.exe"
    }
}

$root   = "blender\out\cine"
$out    = "sepang_cine_highlight.mp4"
$concat = "$root\concat_list.txt"
$fps    = 24

# Shot order is the edit order. Folder names carry the shot number so the
# sequence is explicit rather than depending on directory sort behaviour.
$shots = @(
    '01_aerial_establish',   # ACT 1 - DRY POWER
    '02_low_speed_tele',
    '03_onboard_dry',
    '04_t1_braking',
    '05_t15_sweep',
    '06_tyre_detail',
    '07_chase_dry',
    '08_aerial_storm',       # ACT 2 - THE SKY BREAKS
    '09_chase_first_rain',
    '10_spray_tele',
    '11_onboard_rain',
    '12_low_wheel_spray',
    '13_t1_wet_pan',
    '14_chase_battle',
    '15_aerial_monsoon',     # ACT 3 - MONSOON
    '16_onboard_monsoon',
    '17_spray_curtain',
    '18_low_hero_monsoon',
    '19_chase_monsoon',
    '20_tyre_water',
    '21_onboard_climax',
    '22_t15_monsoon_pan',
    '23_chase_final_push',
    '24_hero_beauty_hold'
)

# ── 1. encode each shot ────────────────────────────────────────────────────
# Each shot's frames start at its own source frame number (not 1), so -start_number
# is read from the first file present rather than assumed.
$parts = @()
foreach ($shot in $shots) {
    $dir = Join-Path $root $shot
    if (-not (Test-Path $dir)) {
        Write-Warning "missing shot folder: $dir  (skipping)"
        continue
    }
    $frames = Get-ChildItem -Path $dir -Filter 'f_*.png' | Sort-Object Name
    if ($frames.Count -eq 0) {
        Write-Warning "no frames in: $dir  (skipping)"
        continue
    }
    $first = [int]($frames[0].BaseName -replace '\D', '')
    $dest  = Join-Path $root "$shot.part.mp4"

    Write-Host ("encoding {0,-24} {1,4} frames (from {2})" -f $shot, $frames.Count, $first)
    & $ffmpeg -y -loglevel error `
        -framerate $fps -start_number $first `
        -i (Join-Path $dir 'f_%04d.png') `
        -frames:v $frames.Count `
        -c:v libx264 -crf 17 -preset slow `
        -pix_fmt yuv420p -movflags +faststart `
        $dest
    if ($LASTEXITCODE -ne 0) { throw "ffmpeg failed encoding $shot" }
    $parts += (Resolve-Path $dest).Path
}

if ($parts.Count -eq 0) { throw "nothing encoded - did the render run?" }

# ── 2. concat list ─────────────────────────────────────────────────────────
$parts | ForEach-Object { "file '$($_.Replace('\','/'))'" } |
    Set-Content $concat -Encoding ASCII

# ── 3. concatenate (stream copy, no requantising) ─────────────────────────
Write-Host "`nconcatenating $($parts.Count) shots ..."
& $ffmpeg -y -loglevel error -f concat -safe 0 -i $concat -c copy $out
if ($LASTEXITCODE -ne 0) { throw "ffmpeg failed during concat" }

# ── 4. report ──────────────────────────────────────────────────────────────
$mb  = [math]::Round((Get-Item $out).Length / 1MB, 1)
$dur = (& $ffprobe -v error -show_entries format=duration `
        -of default=noprint_wrappers=1:nokey=1 $out) 2>$null
Write-Host ""
Write-Host "Done: $out"
Write-Host "Size: $mb MB"
if ($dur) { Write-Host ("Duration: {0:N2} s" -f [double]$dur) }
