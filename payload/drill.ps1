param([Parameter(Mandatory=$true)][string]$Root)
[Console]::OutputEncoding=[Text.Encoding]::UTF8

function DirBytes([string]$p){
  if(-not (Test-Path -LiteralPath $p)){ return -2 }
  $o = robocopy $p NULL /L /S /BYTES /XJ /R:0 /W:0 /NFL /NDL /NP
  $m = $o | Select-String -Pattern '^\s*Bytes\s*:\s*([0-9,]+)' | Select-Object -First 1
  if($m){ return [int64]($m.Matches[0].Groups[1].Value -replace ',','') }
  return -1
}

"### $Root"
$res=@()
Get-ChildItem -LiteralPath $Root -Directory -Force -ErrorAction SilentlyContinue | Where-Object {
  -not ($_.Attributes -band [IO.FileAttributes]::ReparsePoint)
} | ForEach-Object { $res += [PSCustomObject]@{ Path=$_.Name; Bytes=(DirBytes $_.FullName) } }
$res | Sort-Object Bytes -Descending | Where-Object { $_.Bytes -gt 100MB } | ForEach-Object {
  "{0,9:N2} GB  {1}" -f ($_.Bytes/1GB), $_.Path
}
