$ErrorActionPreference = "Stop"

$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

Set-Location $PSScriptRoot\..

Write-Host "BizNews JP publish script" -ForegroundColor Cyan

gh auth status *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "GitHub login is required." -ForegroundColor Yellow
    Write-Host "Run: gh auth login --hostname github.com --git-protocol https --web"
    exit 1
}

$repoName = "biz-news-jp"
$visibility = "public"

Write-Host "Creating GitHub repository and pushing..." -ForegroundColor Green
gh repo create $repoName --$visibility --source=. --remote=origin --push

if ($LASTEXITCODE -ne 0) {
    Write-Host "Repository creation failed. If it already exists, try:" -ForegroundColor Yellow
    Write-Host "  git remote add origin https://github.com/<your-user>/$repoName.git"
    Write-Host "  git push -u origin master"
    exit 1
}

$repoUrl = gh repo view --json url -q .url
Write-Host ""
Write-Host "GitHub repository:" $repoUrl -ForegroundColor Green
Write-Host ""
Write-Host "Next: deploy on Render" -ForegroundColor Cyan
Write-Host "1. Open https://dashboard.render.com/blueprints"
Write-Host "2. Connect this GitHub repository"
Write-Host "3. Set environment variable BASE_URL to your Render URL"
Write-Host "   Example: https://biz-news-jp.onrender.com"
Write-Host "4. Deploy"
