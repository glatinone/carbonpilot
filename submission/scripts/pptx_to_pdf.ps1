# Export CarbonPilot deck to PDF (fonts embedded) + render slide PNGs for QA.
param(
  [string]$Deck = "C:\Users\kiell.tampubolon\Videos\Claude Code Project\japac\carbonpilot\submission\CarbonPilot_submission_deck.pptx",
  [string]$OutDir = "C:\Users\kiell.tampubolon\Videos\Claude Code Project\japac\carbonpilot\submission"
)
$ErrorActionPreference = "Stop"
$pp = New-Object -ComObject PowerPoint.Application
try {
  $pres = $pp.Presentations.Open($Deck, $true, $false, $false)
  $renderDir = Join-Path $OutDir "render"
  New-Item -ItemType Directory -Force -Path $renderDir | Out-Null
  for ($i = 1; $i -le $pres.Slides.Count; $i++) {
    $pres.Slides.Item($i).Export((Join-Path $renderDir ("slide-{0:D2}.png" -f $i)), "PNG", 1600, 900)
  }
  $pdf = Join-Path $OutDir "CarbonPilot_submission_deck.pdf"
  $pres.SaveAs($pdf, 32)  # 32 = ppSaveAsPDF
  Write-Output ("PDF: " + $pdf)
  Write-Output ("Slides: " + $pres.Slides.Count)
  $pres.Close()
} finally {
  $pp.Quit()
  [System.Runtime.InteropServices.Marshal]::ReleaseComObject($pp) | Out-Null
}