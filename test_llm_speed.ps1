# Test LLM speed with different token counts
Write-Host "=" * 60
Write-Host "LLM PERFORMANCE TEST - qwen3-vl:235b-instruct-cloud"
Write-Host "=" * 60

$body = @{
    model = "qwen3-vl:235b-instruct-cloud"
    prompt = "Write a comprehensive essay about self-worth, discernment, and personal growth. Cover: 1) The foundation of self-worth, 2) How discernment develops, 3) The relationship between them, 4) Practical applications, 5) Common challenges. Be thorough and detailed."
    stream = $false
    options = @{
        num_predict = 2500
    }
} | ConvertTo-Json -Depth 3

Write-Host "`nSending request for ~2500 tokens..."
$sw = [System.Diagnostics.Stopwatch]::StartNew()

try {
    $response = Invoke-RestMethod -Uri "http://localhost:11434/api/generate" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 300
    $sw.Stop()

    Write-Host "`nRESULTS:"
    Write-Host "--------"
    Write-Host "Total Time: $([math]::Round($sw.Elapsed.TotalSeconds, 2)) seconds"
    Write-Host "Prompt Tokens: $($response.prompt_eval_count)"
    Write-Host "Response Tokens: $($response.eval_count)"
    Write-Host "Total Duration (Ollama): $([math]::Round($response.total_duration / 1e9, 2))s"

    if ($response.eval_duration -gt 0) {
        $tokPerSec = $response.eval_count / ($response.eval_duration / 1e9)
        Write-Host "Token Rate: $([math]::Round($tokPerSec, 1)) tokens/second"
    }

    Write-Host "`nResponse Preview (first 300 chars):"
    Write-Host $response.response.Substring(0, [Math]::Min(300, $response.response.Length))
    Write-Host "..."
}
catch {
    $sw.Stop()
    Write-Host "ERROR: $_"
    Write-Host "Time before error: $([math]::Round($sw.Elapsed.TotalSeconds, 2))s"
}

Write-Host "`n" + "=" * 60
