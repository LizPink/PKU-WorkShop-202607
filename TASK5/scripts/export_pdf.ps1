param(
    [Parameter(Mandatory = $true)]
    [string]$InputDocx,
    [Parameter(Mandatory = $true)]
    [string]$OutputPdf
)

$inputPath = (Resolve-Path -LiteralPath $InputDocx).Path
$outputPath = [System.IO.Path]::GetFullPath($OutputPdf)
$reportRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\report"))

if (-not $outputPath.StartsWith($reportRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "PDF output must stay inside TASK5 report directory."
}

$outputDirectory = Split-Path -Parent $outputPath
if (-not (Test-Path -LiteralPath $outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory | Out-Null
}

$word = $null
$document = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $document = $word.Documents.Open($inputPath, $false, $true)
    $document.ExportAsFixedFormat($outputPath, 17)
    Write-Output "PDF created: $outputPath"
}
finally {
    if ($null -ne $document) {
        $document.Close($false)
        [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($document)
    }
    if ($null -ne $word) {
        $word.Quit()
        [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($word)
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
