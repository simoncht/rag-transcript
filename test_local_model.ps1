# Test LOCAL model speed
Write-Host "=" * 60
Write-Host "LOCAL MODEL TEST - llama3.1:latest"
Write-Host "=" * 60

$body = @{
    model = "llama3.1:latest"
    prompt = "Write a comprehensive essay about self-worth and discernment. Cover key concepts and practical applications."
    stream = $false
    options = @{
        num_predict = 500  # Smaller to test speed
    }
} | ConvertTo-Json -Depth 3

Write-Host "`nSending request for ~500 tokens..."
$sw = [System.Diagnostics.Stopwatch]::StartNew()

try {
    $response = Invoke-RestMethod -Uri "http://localhost:11434/api/generate" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 300
    $sw.Stop()

    Write-Host "`nRESULTS:"
    Write-Host "--------"
    Write-Host "Total Time: $([math]::Round($sw.Elapsed.TotalSeconds, 2)) seconds"
    Write-Host "Response Tokens: $($response.eval_count)"

    if ($response.eval_duration -gt 0) {
        $tokPerSec = $response.eval_count / ($response.eval_duration / 1e9)
        Write-Host "Token Rate: $([math]::Round($tokPerSec, 1)) tokens/second"
    }
}
catch {
    $sw.Stop()
    Write-Host "ERROR: $_"
}

Write-Host "`n" + "=" * 60
