@echo off
cd /d "%~dp0"
"%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe" /nologo /target:winexe /optimize+ /platform:anycpu /codepage:65001 ^
  /win32icon:Harness.ico ^
  /r:%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\System.dll ^
  /r:%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\System.Core.dll ^
  /r:%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\System.Windows.Forms.dll ^
  /r:%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\System.Drawing.dll ^
  /r:%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\System.Web.Extensions.dll ^
  /out:Harness.exe launcher.cs
echo.
echo Done: Harness.exe created in %~dp0
pause
