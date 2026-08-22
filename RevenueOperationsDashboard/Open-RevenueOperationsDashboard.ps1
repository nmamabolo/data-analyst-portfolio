$ErrorActionPreference = 'Stop'
$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$workbookPath = Join-Path $projectDir 'Data\revenue_operations_portfolio_data.xlsx'
$modelFile = Join-Path $projectDir 'RevenueOperations.SemanticModel\definition\model.tmdl'
$content = Get-Content -LiteralPath $modelFile -Raw
$escapedPath = $workbookPath.Replace('"', '""')
$content = [regex]::Replace($content, 'expression SourceWorkbookPath = "[^"]*"', 'expression SourceWorkbookPath = "' + $escapedPath + '"')
Set-Content -LiteralPath $modelFile -Value $content -Encoding utf8
Start-Process -FilePath (Join-Path $projectDir 'RevenueOperations.pbip')
