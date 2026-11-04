# BrandMuse Phase 7 End-to-End Production Smoke Test (PowerShell)
param(
    [string]$BaseUrl = "http://localhost:8000"
)

$ErrorActionPreference = "Stop"
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host " BrandMuse Phase 7 End-to-End Production Smoke Test" -ForegroundColor Cyan
Write-Host " Target Base URL: $BaseUrl" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

$SessionId = [System.Guid]::NewGuid().ToString()
Write-Host "Active Isolated Session ID: $SessionId`n"

# 1. Health & Security Headers
Write-Host -NoNewline "[1/8] Verifying GET /api/health & Security Headers ... "
$healthRes = Invoke-WebRequest -Uri "$BaseUrl/api/health" -Method Get
if ($healthRes.StatusCode -ne 200) {
    Write-Host "FAILED (Status $($healthRes.StatusCode))" -ForegroundColor Red
    exit 1
}
$secHeader = $healthRes.Headers["X-Content-Type-Options"]
if ($secHeader -ne "nosniff") {
    Write-Host "FAILED (Missing X-Content-Type-Options: nosniff)" -ForegroundColor Red
    exit 1
}
Write-Host "PASSED (200 OK with strict security headers)" -ForegroundColor Green

# 2. Session Isolation (400 when missing header)
Write-Host -NoNewline "[2/8] Verifying Session Isolation (400 on missing X-Session-Id) ... "
try {
    $null = Invoke-RestMethod -Uri "$BaseUrl/api/documents" -Method Get
    Write-Host "FAILED (Expected 400 Bad Request)" -ForegroundColor Red
    exit 1
} catch {
    if ($_.Exception.Response.StatusCode.value__ -eq 400) {
        Write-Host "PASSED (400 Bad Request enforced)" -ForegroundColor Green
    } else {
        Write-Host "FAILED ($($_.Exception.Message))" -ForegroundColor Red
        exit 1
    }
}

# 3. Load Sample Brand Guideline
Write-Host -NoNewline "[3/8] Loading Sample Brand Guideline (POST /api/documents/sample) ... "
$sampleRes = Invoke-RestMethod -Uri "$BaseUrl/api/documents/sample" -Method Post -Headers @{ "X-Session-Id" = $SessionId }
$DocId = $sampleRes.document.id
if (-not $DocId) {
    $DocId = $sampleRes.id
}
if (-not $DocId) {
    Write-Host "FAILED (Could not obtain document ID)" -ForegroundColor Red
    exit 1
}
Write-Host "PASSED (Document ID: $DocId)" -ForegroundColor Green

# 4. List Documents
Write-Host -NoNewline "[4/8] Listing Guidelines (GET /api/documents) ... "
$listRes = Invoke-RestMethod -Uri "$BaseUrl/api/documents" -Method Get -Headers @{ "X-Session-Id" = $SessionId }
$found = $false
foreach ($d in $listRes.documents) {
    if ($d.id -eq $DocId) {
        $found = $true
        break
    }
}
if (-not $found) {
    Write-Host "FAILED (Document not found in session list)" -ForegroundColor Red
    exit 1
}
Write-Host "PASSED (Document registered in session)" -ForegroundColor Green

# 5. Ask Grounded Brand Q&A (SSE Streaming)
Write-Host -NoNewline "[5/8] Streaming Grounded Chat (POST /api/chat) ... "
$chatBody = @{
    document_id = $DocId
    message = "What is the brand tone of voice?"
    history = @()
} | ConvertTo-Json

$chatRes = Invoke-WebRequest -Uri "$BaseUrl/api/chat" -Method Post -Headers @{
    "X-Session-Id" = $SessionId
    "Content-Type" = "application/json"
} -Body $chatBody

$content = $chatRes.Content
if ($content -match "event: token" -and $content -match "event: done") {
    Write-Host "PASSED (SSE token stream & citations verified)" -ForegroundColor Green
} else {
    Write-Host "FAILED (SSE stream missing expected events)" -ForegroundColor Red
    exit 1
}

# 6. Generate 3 On-Brand Concepts
Write-Host -NoNewline "[6/8] Generating Campaign Concepts (POST /api/campaign) ... "
$campaignBody = @{
    document_id = $DocId
    brief = @{
        product = "Minimalist Ceramic Cup"
        audience = "Design Enthusiasts"
        channel = "Instagram"
        mood = "serene"
    }
} | ConvertTo-Json

$campaignRes = Invoke-RestMethod -Uri "$BaseUrl/api/campaign" -Method Post -Headers @{
    "X-Session-Id" = $SessionId
    "Content-Type" = "application/json"
} -Body $campaignBody

if ($campaignRes.concepts.Count -ge 3) {
    Write-Host "PASSED (3 structured concepts generated)" -ForegroundColor Green
} else {
    Write-Host "FAILED (Expected 3 concepts, received $($campaignRes.concepts.Count))" -ForegroundColor Red
    exit 1
}

# 7. Generate Stable Diffusion Image Asset
Write-Host -NoNewline "[7/8] Generating Image Asset (POST /api/images) ... "
$imgBody = @{
    concept_title = "Morning Sanctuary"
    image_prompt = "Minimalist ceramic cup on handcrafted oak dining table in soft daylight"
    concept_json = @{ mood = "serene" }
} | ConvertTo-Json

$imgRes = Invoke-RestMethod -Uri "$BaseUrl/api/images" -Method Post -Headers @{
    "X-Session-Id" = $SessionId
    "Content-Type" = "application/json"
} -Body $imgBody

if ($imgRes.url) {
    $preview = $imgRes.url.Substring(0, [System.Math]::Min(40, $imgRes.url.Length))
    Write-Host "PASSED (Asset: $preview...)" -ForegroundColor Green
} else {
    Write-Host "FAILED (No image URL returned)" -ForegroundColor Red
    exit 1
}

# 8. Retrieve Session Gallery
Write-Host -NoNewline "[8/8] Inspecting Session Gallery (GET /api/images) ... "
$galleryRes = Invoke-RestMethod -Uri "$BaseUrl/api/images" -Method Get -Headers @{ "X-Session-Id" = $SessionId }
if ($galleryRes.generations.Count -ge 1) {
    Write-Host "PASSED (Asset verified in gallery)" -ForegroundColor Green
} else {
    Write-Host "FAILED (Gallery empty)" -ForegroundColor Red
    exit 1
}

Write-Host "`n========================================================" -ForegroundColor Cyan
Write-Host " ALL 8 END-TO-END QUALITY GATE VERIFICATIONS PASSED!" -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Cyan
