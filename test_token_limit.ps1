# Test if Ollama cloud respects num_predict parameter
Write-Host "Testing if cloud model respects token limits..."

$tests = @(
    @{limit=50; prompt="Write exactly 2 sentences about self-worth."},
    @{limit=200; prompt="Write a short paragraph about self-worth."},
    @{limit=800; prompt="Write about self-worth and discernment."}
)

foreach ($test in $tests) {
    Write-Host "`n--- Test: num_predict=$($test.limit) ---"

    $body = @{
        model = "qwen3-vl:235b-instruct-cloud"
        prompt = $test.prompt
        stream = $false
        options = @{
            num_predict = $test.limit
        }
    } | ConvertTo-Json -Depth 3

    $sw = [System.Diagnostics.Stopwatch]::StartNew()

    try {
        $response = Invoke-RestMethod -Uri "http://localhost:11434/api/generate" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 120
        $sw.Stop()

        Write-Host "Requested limit: $($test.limit)"
        Write-Host "Actual tokens: $($response.eval_count)"
        Write-Host "Time: $([math]::Round($sw.Elapsed.TotalSeconds, 1))s"

        if ($response.eval_count -gt ($test.limit + 10)) {
            Write-Host "⚠ LIMIT IGNORED - Got $($response.eval_count) tokens (requested $($test.limit))" -ForegroundColor Red
        } else {
            Write-Host "✓ Limit respected" -ForegroundColor Green
        }
    }
    catch {
        Write-Host "ERROR: $_" -ForegroundColor Red
    }
}

Write-Host "`n" + "="*60
Write-Host "CONCLUSION:"
Write-Host "If 'LIMIT IGNORED' appears, the cloud model does not respect num_predict"
Write-Host "="*60
