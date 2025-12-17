# Simple test: Does cloud model respect num_predict?
Write-Host "Test 1: Requesting 100 tokens max"

$body1 = '{
  "model": "qwen3-vl:235b-instruct-cloud",
  "prompt": "Write about self-worth in 2 sentences.",
  "stream": false,
  "options": {"num_predict": 100}
}'

$r1 = Invoke-RestMethod -Uri "http://localhost:11434/api/generate" -Method Post -Body $body1 -ContentType "application/json"
Write-Host "Result: $($r1.eval_count) tokens"

if ($r1.eval_count -gt 150) {
    Write-Host "FAIL: Cloud model IGNORES num_predict limit!" -ForegroundColor Red
} else {
    Write-Host "PASS: Limit respected" -ForegroundColor Green
}

Write-Host "`nTest 2: Requesting 800 tokens max"

$body2 = '{
  "model": "qwen3-vl:235b-instruct-cloud",
  "prompt": "Write a detailed essay about self-worth.",
  "stream": false,
  "options": {"num_predict": 800}
}'

$r2 = Invoke-RestMethod -Uri "http://localhost:11434/api/generate" -Method Post -Body $body2 -ContentType "application/json"
Write-Host "Result: $($r2.eval_count) tokens"

if ($r2.eval_count -gt 900) {
    Write-Host "FAIL: Cloud model IGNORES num_predict limit!" -ForegroundColor Red
} else {
    Write-Host "PASS: Limit respected" -ForegroundColor Green
}
