<#
.SYNOPSIS
  Biên dịch HAI DLL của add-in SAN NỀN (C#) bằng csc.exe của .NET Framework 4.x, theo thứ tự:
    1. cad\dotnet\bin\SanNenDraw.dll    (xay_draw.ps1 — lớp vẽ, không giao diện; chạy được trong accoreconsole)
    2. cad\dotnet\bin\SanNenPalette.dll (palette dock; tham chiếu SanNenDraw.dll)

.DESCRIPTION
  Không cần SDK, NuGet hay Visual Studio. Tham chiếu acmgd.dll, accoremgd.dll, acdbmgd.dll của AutoCAD 2022
  (chỉ để biên dịch, KHÔNG sao chép vào bin). Mã nguồn dùng C# 5 (giới hạn của csc.exe .NET Framework).
  Không sửa registry, không sửa biến hệ thống, không cài gì vào thư mục AutoCAD.

.PARAMETER AutoCAD
  Thư mục cài AutoCAD 2022. Mặc định C:\Program Files\Autodesk\AutoCAD 2022.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File cad\dotnet\xay_palette.ps1
#>
param(
    [string]$AutoCAD = "C:\Program Files\Autodesk\AutoCAD 2022"
)
$ErrorActionPreference = "Stop"
$goc  = $PSScriptRoot
$nguon = Join-Path $goc "SanNenPalette"
$bin  = Join-Path $goc "bin"
$dll  = Join-Path $bin "SanNenPalette.dll"
$csc  = Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\csc.exe"
$drawDll = Join-Path $bin "SanNenDraw.dll"
$wpf  = Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\WPF"

function Loi($m) { Write-Host ("LỖI: " + $m) -ForegroundColor Red; exit 1 }

if (-not (Test-Path $csc)) { Loi "Không thấy csc.exe ($csc). Cần .NET Framework 4.x (có sẵn trên Windows 10)." }
# 1) SanNenDraw.dll trước — palette tham chiếu nó (J, CauHinh, CauNoiPython).
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $goc "xay_draw.ps1") -AutoCAD $AutoCAD
if ($LASTEXITCODE -ne 0) { Loi "Xây SanNenDraw.dll thất bại — dừng, chưa xây palette." }
foreach ($t in "acmgd.dll", "accoremgd.dll", "acdbmgd.dll") {
    if (-not (Test-Path (Join-Path $AutoCAD $t))) { Loi "Không thấy $t trong '$AutoCAD'. Chạy lại với -AutoCAD <thư mục AutoCAD 2022>." }
}
$files = Get-ChildItem -Path $nguon -Filter *.cs -Recurse | Sort-Object FullName | ForEach-Object { $_.FullName }
if (-not $files) { Loi "Không thấy file .cs trong $nguon" }

New-Item -ItemType Directory -Force -Path $bin | Out-Null
# Biên dịch ra file tạm rồi mới thay DLL: nếu AutoCAD đang giữ DLL cũ (đã NETLOAD) thì báo rõ thay vì hỏng DLL.
$tam = Join-Path $bin "SanNenPalette.new.dll"
$rsp = Join-Path $bin "SanNenPalette.rsp"
$dong = @(
    "/nologo", "/target:library", "/optimize+", "/debug:pdbonly", "/codepage:65001", "/utf8output", "/nowarn:1701,1702",
    "/out:`"$tam`"",
    "/reference:`"$(Join-Path $AutoCAD 'acmgd.dll')`"",
    "/reference:`"$(Join-Path $AutoCAD 'accoremgd.dll')`"",
    "/reference:`"$(Join-Path $AutoCAD 'acdbmgd.dll')`"",
    "/reference:`"$drawDll`"",
    "/reference:System.dll", "/reference:System.Core.dll", "/reference:System.Drawing.dll",
    "/reference:System.Windows.Forms.dll", "/reference:System.Web.Extensions.dll",
    "/reference:`"$wpf\PresentationCore.dll`"", "/reference:`"$wpf\WindowsBase.dll`""       # acmgd.dll dùng kiểu WPF (IWin32Window...) trong chữ ký
)
foreach ($f in $files) { $dong += "`"$f`"" }
[System.IO.File]::WriteAllLines($rsp, $dong, (New-Object System.Text.UTF8Encoding($true)))

Write-Host "Biên dịch $($files.Count) file C# bằng $csc ..."
$kq = & $csc "@$rsp" 2>&1 | ForEach-Object { "$_" }
$ma = $LASTEXITCODE
$kq | ForEach-Object { if ($_ -match "error CS") { Write-Host $_ -ForegroundColor Red } elseif ($_ -match "warning CS") { Write-Host $_ -ForegroundColor Yellow } else { Write-Host $_ } }
Remove-Item $rsp -ErrorAction SilentlyContinue
if ($ma -ne 0) { Remove-Item $tam -ErrorAction SilentlyContinue; Loi "Biên dịch thất bại (mã $ma) — xem các dòng 'error CS' ở trên." }

try {
    Move-Item -Force $tam $dll
    $pdb = [System.IO.Path]::ChangeExtension($tam, ".pdb")
    if (Test-Path $pdb) { Move-Item -Force $pdb ([System.IO.Path]::ChangeExtension($dll, ".pdb")) }
} catch {
    Remove-Item $tam -ErrorAction SilentlyContinue
    Loi "Không ghi đè được $dll — AutoCAD đang giữ DLL cũ (đã NETLOAD). Đóng AutoCAD rồi chạy lại. ($($_.Exception.Message))"
}
Write-Host ("XONG: " + $dll) -ForegroundColor Green
Write-Host "Hai DLL phải nằm CÙNG thư mục bin (palette nạp SanNenDraw.dll từ đó)."
Write-Host "Nạp trong AutoCAD: gõ SN_PALETTE (sannen.lsp tự NETLOAD), hoặc NETLOAD thủ công file trên."
Write-Host "Nếu AutoCAD hỏi tin cậy DLL (SECURELOAD): chọn 'Always Load' cho thư mục này, hoặc tự thêm thư mục cad\dotnet\bin vào TRUSTEDPATHS."
