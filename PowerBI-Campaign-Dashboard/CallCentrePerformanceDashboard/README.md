# Call Centre Performance Dashboard

+This is a Power BI Project (PBIP) containing a complete report definition and semantic model. It uses a synthetic portfolio dataset (18,000 calls, 18 agents, 4 queues) covering 2025-09-01 through 2026-08-09. No real customer or employee data is included.

+## Open the dashboard
+
+1. Install a current version of Power BI Desktop.
+2. Right-click **Open-CallCentreDashboard.ps1** and choose **Run with PowerShell**. The helper updates the workbook path after the folder is moved, then opens the PBIP project.
+3. In Power BI Desktop, select **Refresh** if prompted.
+4. Choose **File > Save As > Power BI report (.pbix)** to create the requested PBIX file.
+
+You can also open **CallCentrePerformance.pbip** directly. If the project was moved, update the **SourceWorkbookPath** Power Query parameter to the included workbook under **Data**.
+
+## Report contents
+
+- **Executive Overview:** Five individual KPI cards for total/answered calls, SLA, abandonment and AHT, plus hourly demand, monthly volume and queue outcomes.
+- **Agent Performance:** Agent volume, AHT, SLA, CSAT, FCR, team filtering, and a sortable scorecard.
+- **Queue & Trends:** Queue scorecard plus weekly volume and monthly service-level trends.
+
+## Metric definitions
+
+- **AHT:** (Talk Seconds + After Call Seconds) / Answered Calls, shown in minutes.
+- **SLA Rate:** Answered calls within the queue-specific target / Answered Calls.
+- **Abandonment Rate:** Abandoned Calls / Total Calls.
+- **FCR Rate:** Answered calls resolved on first contact / Answered Calls.
+