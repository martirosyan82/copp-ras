# ==============================================================================
# quick_push.ps1 — Скрипт быстрого коммита и пуша изменений в Git для Windows
# Использование:
#   .\quick_push.ps1
#   .\quick_push.ps1 -Message "Описание изменений"
# ==============================================================================

[CmdletBinding()]
param (
    [Parameter(Position = 0)]
    [string]$Message = ""
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host ""
Write-Host "══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  COPP-RAS — Быстрый пуш изменений в Git (PowerShell)    " -ForegroundColor Cyan
Write-Host "══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# 1. Проверка наличия Git
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "[ОШИБКА] Git не найден в PATH! Убедитесь, что Git установлен." -ForegroundColor Red
    pause
    exit 1
}

# 2. Определение текущей ветки
$branch = (git branch --show-current 2>$null)
if (-not $branch) {
    $branch = "main"
}

# 3. Проверка статуса репозитория
$status = (git status --porcelain 2>$null)

if (-not $status) {
    Write-Host "[ИНФО] Изменений в рабочей директории нет. Всё чисто." -ForegroundColor Yellow
    Write-Host ""
    pause
    exit 0
}

Write-Host "Измененные файлы:" -ForegroundColor Yellow
git status --short
Write-Host ""

# 4. Запрос комментария к коммиту
if (-not $Message) {
    $Message = Read-Host "Введите комментарий к коммиту (Enter для авто-даты)"
}

if (-not $Message) {
    $now = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $Message = "Update: $now"
}

# 5. Индексация и защита базы данных / секретов
Write-Host ""
Write-Host ">> [1/3] Индексация файлов..." -ForegroundColor Cyan
git add .

# Снимаем с коммита локальную базу данных, временные файлы и секреты
git reset HEAD reports.db* 2>$null
git reset HEAD *.sqlite* 2>$null
git reset HEAD *.bak 2>$null
git reset HEAD .secret_key 2>$null
git reset HEAD .env 2>$null

# 6. Создание коммита
Write-Host ">> [2/3] Создание коммита: '$Message'..." -ForegroundColor Cyan
git commit -m "$Message"
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ОШИБКА] Не удалось создать коммит." -ForegroundColor Red
    pause
    exit 1
}

# 7. Отправка в Git-сервер
Write-Host ""
Write-Host ">> [3/3] Отправка изменений в ветку '$branch'..." -ForegroundColor Cyan
git push origin $branch
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "[ОШИБКА] Не удалось выполнить git push!" -ForegroundColor Red
    Write-Host "Проверьте соединение с GitHub и права доступа." -ForegroundColor Yellow
    pause
    exit 1
}

Write-Host ""
Write-Host "══════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host "  [OK] УСПЕШНО ОТПРАВЛЕНО В РЕПОЗИТОРИЙ (ветка: $branch)!" -ForegroundColor Green
Write-Host "══════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host ""
Write-Host "Для применения обновления на сервере выполните:" -ForegroundColor Cyan
Write-Host "  cd /var/www/copp-ras && sudo bash update.sh" -ForegroundColor White
Write-Host ""
pause
