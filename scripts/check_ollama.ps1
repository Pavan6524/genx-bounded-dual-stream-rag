$p = Get-Process -Name ollama -ErrorAction SilentlyContinue
if ($p) {
    Write-Host "Found Ollama process: ID=$($p.Id) Name=$($p.ProcessName)"
} else {
    Write-Host "No Ollama process found."
}

$conn = Get-NetTCPConnection -LocalPort 11434 -State Listen -ErrorAction SilentlyContinue
if ($conn) {
    Write-Host "Port 11434 is LISTENING on IP=$($conn.LocalAddress):$($conn.LocalPort)"
} else {
    Write-Host "Port 11434 is NOT listening."
}
