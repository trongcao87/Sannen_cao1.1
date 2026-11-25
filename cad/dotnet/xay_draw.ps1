<#
.SYNOPSIS
  Biên dịch SanNenDraw.dll (C#) — lớp VẼ không phụ thuộc giao diện — bằng csc.exe của .NET Framework 4.x.

.DESCRIPTION
  Chỉ tham chiếu accoremgd.dll và acdbmgd.dll của AutoCAD 2022 (KHÔNG acmgd.dll, KHÔNG WinForms/WPF) nên NETLOAD được trong
  accoreconsole.exe (kiểm thử không giao diện) lẫn AutoCAD thường. Mã nguồn dùng C# 5. Không cần SDK/NuGet, không sửa registry.
  Ra: cad\dotnet\bin\SanNenDraw.dll. Palette (xay_palette.ps1) tham chiếu DLL này nên script đó gọi file này TRƯỚC.

.PARAMETER AutoCAD
  Thư mục cài AutoCAD 2022. Mặc định C:\Program Files\Autodesk\AutoCAD 2022.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File cad\dotnet\xay_draw.ps1
#>
param(
    [string]$AutoCAD = "C:\Program Files\Autodesk\AutoCAD 2022"
)
$ErrorActionPreference = "Stop"
$goc  = $PSScriptRoot
$nguon = Join-Path $goc "SanNenDraw"
$bin  = Join-Path $goc "bin"
$dll  = Join-Path $bin "SanNenDraw.dll"
$csc  = Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\csc.exe"

function Loi($m) { Write-Host ("LỖI: " + $m) -ForegroundColor Red; exit 1 }

if (-not (Test-Path $csc)) { Loi "Không thấy csc.exe ($csc). Cần .NET Framework 4.x (có sẵn trên Windows 10)." }
foreach ($t in "accoremgd.dll", "acdbmgd.dll") {
    if (-not (Test-Path (Join-Path $AutoCAD $t))) { Loi "Không thấy $t trong '$AutoCAD'. Chạy lại với -AutoCAD <thư mục AutoCAD 2022>." }
}
$files = Get-ChildItem -Path $nguon -Filter *.cs -Recurse | Sort-Object FullName | ForEach-Object { $_.FullName }
if (-not $files) { Loi "Không thấy file .cs trong $nguon" }

$binTam = Join-Path $bin "_build"
New-Item -ItemType Directory -Force -Path $bin | Out-Null
New-Item -ItemType Directory -Force -Path $binTam | Out-Null
# Biên dịch ra thư mục tạm với đúng tên SanNenDraw.dll (để AssemblyName là "SanNenDraw", thay vì SanNenDraw.new.dll):
$tam = Join-Path $binTam "SanNenDraw.dll"
$rsp = Join-Path $bin "SanNenDraw.rsp"
$dong = @(
    "/nologo", "/target:library", "/optimize+", "/debug:pdbonly", "/codepage:65001", "/utf8output", "/nowarn:1701,1702",
    "/out:`"$tam`"",
    "/reference:`"$(Join-Path $AutoCAD 'accoremgd.dll')`"",
    "/reference:`"$(Join-Path $AutoCAD 'acdbmgd.dll')`"",
    "/reference:System.dll", "/reference:System.Core.dll", "/reference:System.Web.Extensions.dll"
)
foreach ($f in $files) { $dong += "`"$f`"" }
[System.IO.File]::WriteAllLines($rsp, $dong, (New-Object System.Text.UTF8Encoding($true)))

Write-Host "Biên dịch SanNenDraw: $($files.Count) file C# bằng $csc ..."
$kq = & $csc "@$rsp" 2>&1 | ForEach-Object { "$_" }
$ma = $LASTEXITCODE
$kq | ForEach-Object { if ($_ -match "error CS") { Write-Host $_ -ForegroundColor Red } elseif ($_ -match "warning CS") { Write-Host $_ -ForegroundColor Yellow } else { Write-Host $_ } }
Remove-Item $rsp -ErrorAction SilentlyContinue
if ($ma -ne 0) { Remove-Item $tam -ErrorAction SilentlyContinue; Loi "Biên dịch SanNenDraw thất bại (mã $ma) — xem các dòng 'error CS' ở trên." }

try {
    Move-Item -Force $tam $dll
    $pdb = [System.IO.Path]::ChangeExtension($tam, ".pdb")
    if (Test-Path $pdb) { Move-Item -Force $pdb ([System.IO.Path]::ChangeExtension($dll, ".pdb")) }
} catch {
    Remove-Item $tam -ErrorAction SilentlyContinue
    Loi "Không ghi đè được $dll — AutoCAD đang giữ DLL cũ (đã NETLOAD). Đóng AutoCAD rồi chạy lại. ($($_.Exception.Message))"
}
Write-Host ("XONG: " + $dll) -ForegroundColor Green
Write-Host "Lệnh .NET: SN_VE_NET, SN_XOA_NET, SN_XOA_NET_Y, SN_TIN3D_NET, SN_KEHOACH_NET (sannen.lsp tự NETLOAD khi dùng SN_VE / SN_XOA / SN_TIN3D)."