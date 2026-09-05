# Stitch the onboard + chase POV shots from the cinematic highlight into their
# own "driver's eye" clip: dry -> rain -> monsoon -> climax, in story order.
# Each act pairs its chase shot (car seen from behind) with its onboard shot
# (car seen from the cockpit), so POV alternates but stays chronological.
#
# Requires the frames from cine_render.py to already exist under
# blender\out\cine\<NN>_{onboard,chase}_*\f_####.png
#
# Run from:  c:\Users\spoop\OneDrive\Documents\Class\hackathon\F1

$ErrorActionPreference = 'Stop'

$ffmpeg  = "ffmpeg"
$ffprobe = "ffprobe"
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    $fallback = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" `
        -Directory -Filter "Gyan.FFmpeg*" -ErrorAction SilentlyContinue |
        ForEach-Object { Get-ChildItem $_.FullName -Recurse -Filter "ffmpeg.exe" -ErrorAction SilentlyContinue } |
        Select-Object -First 1
    if ($fallback) {
        $ffmpeg  = $fallback.FullName
        $ffprobe = Join-Path $fallback.Directory.FullName "ffprobe.exe"
    }
}

$root   = "blender\out\cine"
$out    = "sepang_pov_reel.mp4"
$concat = "$root\concat_onboard.txt"
$fps    = 24

# Story order: dry -> first rain -> battle -> monsoon -> climax
# Chase and onboard alternate within each act so the cut keeps moving between
# "watching the car" and "riding in the car" while staying chronological.
$shots = @(
    '07_chase_dry',
    '03_onboard_dry',
    '09_chase_first_rain',
    '11_onboard_rain',
    '14_chase_battle',
    '19_chase_monsoon',
    '16_onboard_monsoon',
    '23_chase_final_push',
    '21_onboard_climax'
)

$parts = @()
foreach ($shot in $shots) {
    $dir = Join-Path $root $shot
    if (-not (Test-Path $dir)) { throw "missing shot folder: $dir" }
    $frames = Get-ChildItem -Path $dir -Filter 'f_*.png' | Sort-Object Name
    if ($frames.Count -eq 0) { throw "no frames in: $dir" }
    $first = [int]($frames[0].BaseName -replace '\D', '')
    $dest  = Join-Path $root "$shot.onboard_part.mp4"

    Write-Host ("encoding {0,-20} {1,4} frames (from {2})" -f $shot, $frames.Count, $first)
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

$parts | ForEach-Object { "file '$($_.Replace('\','/'))'" } |
    Set-Content $concat -Encoding ASCII

Write-Host "`nconcatenating $($parts.Count) onboard shots ..."
& $ffmpeg -y -loglevel error -f concat -safe 0 -i $concat -c copy $out
if ($LASTEXITCODE -ne 0) { throw "ffmpeg failed during concat" }

$mb  = [math]::Round((Get-Item $out).Length / 1MB, 1)
$dur = (& $ffprobe -v error -show_entries format=duration `
        -of default=noprint_wrappers=1:nokey=1 $out) 2>$null
Write-Host ""
Write-Host "Done: $out"
Write-Host "Size: $mb MB"
if ($dur) { Write-Host ("Duration: {0:N2} s" -f [double]$dur) }
