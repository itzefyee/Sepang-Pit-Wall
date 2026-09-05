# Mux the real-engine audio onto the three rendered highlight clips.
#
# Pipeline:
#   1. blender\cine_render.py                        -> 1440 PNG frames
#   2. stitch_cine.ps1 / stitch_onboard.ps1          -> silent mp4s
#   3. blender\extract_audio_telemetry.py            -> audio_telemetry.json
#   4. python scripts\synth_audio.py --reel <r> --no-engine   (x3, atmosphere)
#   5. python scripts\apply_real_engine.py           -> sepang_real_<r>.wav
#   6. .\mux_audio.ps1                               -> final mp4s
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

# silent video                        real-engine audio                        output
$jobs = @(
    @{ v = "sepang_cine_highlight.mp4"
       a = "blender\out\sepang_real_full.wav"
       o = "sepang_highlight_final.mp4" },
    @{ v = "sepang_pov_reel.mp4"
       a = "blender\out\sepang_real_pov.wav"
       o = "sepang_pov_final.mp4" },
    @{ v = "sepang_onboard_reel.mp4"
       a = "blender\out\sepang_real_onboard.wav"
       o = "sepang_onboard_final.mp4" }
)

foreach ($j in $jobs) {
    if (-not (Test-Path $j.v)) { Write-Warning "missing video: $($j.v)"; continue }
    if (-not (Test-Path $j.a)) { Write-Warning "missing audio: $($j.a)"; continue }

    Write-Host "muxing $($j.v) + $(Split-Path $j.a -Leaf) -> $($j.o)"
    # Video is stream-copied (no requantising); audio encoded to AAC 320k.
    # -shortest guards against any drift between the two durations.
    & $ffmpeg -y -loglevel error `
        -i $j.v -i $j.a `
        -c:v copy -c:a aac -b:a 320k -ac 2 `
        -map 0:v:0 -map 1:a:0 `
        -movflags +faststart -shortest `
        $j.o
    if ($LASTEXITCODE -ne 0) { throw "ffmpeg failed muxing $($j.o)" }
}

Write-Host ""
Write-Host "Final deliverables:"
foreach ($j in $jobs) {
    if (-not (Test-Path $j.o)) { continue }
    $mb  = [math]::Round((Get-Item $j.o).Length / 1MB, 1)
    $vd  = & $ffprobe -v error -select_streams v:0 -show_entries stream=duration `
             -of default=nw=1:nk=1 $j.o
    $ad  = & $ffprobe -v error -select_streams a:0 -show_entries stream=duration `
             -of default=nw=1:nk=1 $j.o
    $ac  = & $ffprobe -v error -select_streams a:0 -show_entries stream=codec_name `
             -of default=nw=1:nk=1 $j.o
    Write-Host ("  {0,-30} {1,6} MB  video {2,6:N2}s  audio {3,6:N2}s ({4})" -f `
        $j.o, $mb, [double]$vd, [double]$ad, $ac)
}
