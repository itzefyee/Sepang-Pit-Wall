# Stitch the 6 rendered segments into a single highlight mp4.
# Run this AFTER render_highlight.py has finished.
#
# Requirements: ffmpeg on PATH  (winget install --id Gyan.FFmpeg -e)
# Run from:     c:\Users\spoop\OneDrive\Documents\Class\hackathon\F1

$ErrorActionPreference = 'Stop'

$root   = "blender\out\highlight"
$out    = "sepang_highlight.mp4"
$concat = "blender\out\highlight\concat_list.txt"

# Order: T1 braking -> pit blast -> T15 hairpin -> rain -> monsoon -> onboard
$segments = @(
    'seg_B_t1',
    'seg_A_pit',
    'seg_C_t15',
    'seg_D_rain',
    'seg_E_monsoon',
    'seg_F_onboard'
)

# ── 1. encode each segment to a temp mp4 ──────────────────────────────────
$parts = @()
foreach ($seg in $segments) {
    $src  = "$root\$seg\frame_%04d.png"
    $dest = "$root\${seg}_part.mp4"
    Write-Host "Encoding $seg ..."
    & ffmpeg -y -r 24 -i $src `
        -c:v libx264 -crf 18 -preset fast `
        -pix_fmt yuv420p -movflags +faststart `
        $dest
    $parts += $dest
}

# ── 2. write concat list ───────────────────────────────────────────────────
$lines = $parts | ForEach-Object { "file '$($_.Replace('\','/'))'" }
$lines | Set-Content $concat -Encoding ASCII

# ── 3. concatenate without re-encoding ────────────────────────────────────
Write-Host "`nConcatenating segments..."
& ffmpeg -y -f concat -safe 0 -i $concat -c copy $out

Write-Host ""
Write-Host "Done. Output: $out"
$mb = [math]::Round((Get-Item $out).Length / 1MB, 1)
Write-Host "File size: $mb MB"
