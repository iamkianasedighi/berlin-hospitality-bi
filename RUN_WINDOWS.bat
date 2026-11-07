@echo off
setlocal
cd /d "%~dp0"
echo ---------------------------------------------
echo Berlin Hospitality BI - local validation

echo ---------------------------------------------
py -3 -m unittest discover -s tests -v
if errorlevel 1 (
  echo Tests failed. See the error above.
  pause
  exit /b 1
)
py -3 -m pipeline.build_market
if errorlevel 1 (
  echo If the download was blocked, download the Berlin detailed listings.csv.gz manually.
  echo Save it under data\raw\berlin_2026-09-19_listings.csv.gz and run again.
  pause
  exit /b 1
)
echo.
echo Build passed. Review build\quality_report.json before opening the Power BI project.
echo Open powerbi\Berlin_Hospitality\Berlin_Hospitality.pbip
pause
