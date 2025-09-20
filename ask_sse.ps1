param(
  [Parameter(Mandatory=$true)][string]$Question,
  [string]$Url = "http://localhost:8000/api/chat",
  [int]$K = 5,
  [string]$Session = "demo",
  [switch]$ShowSources,
  [switch]$Raw,
  [switch]$NoAggressive
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Fix-Spacing([string]$s) {
  $s = $s -replace "`r",""
  $s = $s -replace "\s{2,}"," "
  $s = $s -replace "\s+([,.;:!\?…])",'$1'
  $s = $s -replace "([(\[\{])\s+",'$1'
  $s = $s -replace "\s+([)\]\}])",'$1'
  return $s.Trim()
}

function Join-MicroChunks([string]$s) {
  $parts = $s -split ' '
  if ($parts.Count -le 1) { return $s }
  $sb = New-Object System.Text.StringBuilder
  foreach ($p in $parts) {
    if ($sb.Length -eq 0) { [void]$sb.Append($p); continue }
    # Se a palavra anterior termina com >=4 letras e a atual tem 1-3 letras, junta sem espaco
    $prev = $sb.ToString()
    $m = [regex]::Match($prev, '\p{L}+$')
    $canJoin = $false
    if ($m.Success -and $m.Value.Length -ge 4 -and ($p -match '^\p{L}{1,3}$')) { $canJoin = $true }
    if ($canJoin) { [void]$sb.Append($p) } else { [void]$sb.Append(' ' + $p) }
  }
  return (Fix-Spacing $sb.ToString())
}

# Monta processo do curl (streaming SSE)
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = 'curl.exe'
$psi.Arguments = ('-sS -N -H "Accept: text/event-stream" --get "{0}" --data-urlencode "q={1}" --data-urlencode "k={2}" --data-urlencode "sessionId={3}"' -f $Url, $Question, $K, $Session)
$psi.UseShellExecute = $false
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$psi.CreateNoWindow = $true
if ($psi.PSObject.Properties.Name -contains 'StandardOutputEncoding') {
  $psi.StandardOutputEncoding = [System.Text.Encoding]::UTF8
  $psi.StandardErrorEncoding  = [System.Text.Encoding]::UTF8
}

$proc = New-Object System.Diagnostics.Process
$proc.StartInfo = $psi
$null = $proc.Start()

$tokens  = New-Object System.Text.StringBuilder
$sources = New-Object System.Text.StringBuilder
$lastEvent = $null

while (-not $proc.HasExited -or -not $proc.StandardOutput.EndOfStream) {
  $line = $proc.StandardOutput.ReadLine()
  if ($null -eq $line) { Start-Sleep -Milliseconds 10; continue }
  if ($line.StartsWith(':')) { continue }            # heartbeat
  if ($line.StartsWith('event:')) { $lastEvent = $line.Substring(6).Trim(); continue }
  if ($line.StartsWith('data:'))  {
    $data = $line.Substring(5)
    if ($lastEvent -eq 'token')   { [void]$tokens.Append($data) }
    elseif ($ShowSources -and $lastEvent -eq 'sources') {
      if ($sources.Length -gt 0) { [void]$sources.AppendLine() }
      [void]$sources.Append($data)
    }
    continue
  }
}

# Saida
$text = $tokens.ToString()
if (-not $Raw) {
  $text = Fix-Spacing $text
  if (-not $NoAggressive) { $text = Join-MicroChunks $text }
}
Write-Output $text

if ($ShowSources -and $sources.Length -gt 0) {
  Write-Output ''
  Write-Output '----- sources -----'
  try {
    ($sources.ToString() | ConvertFrom-Json | ConvertTo-Json -Depth 8)
  } catch {
    Write-Output $sources.ToString()
  }
}

$stderr = $proc.StandardError.ReadToEnd()
if ($stderr) { [Console]::Error.WriteLine($stderr) }
