-- Healthcare Appointment No-Shows | PostgreSQL 13+
DROP SCHEMA IF EXISTS portfolio_09 CASCADE;
CREATE SCHEMA portfolio_09;
SET search_path TO portfolio_09;

CREATE TABLE appointments (appointment_id INT PRIMARY KEY, patient_id INT, provider TEXT, scheduled_at TIMESTAMP, appointment_at TIMESTAMP, status TEXT, sms_reminder BOOLEAN);
INSERT INTO appointments VALUES
(1,1,'Dr. Lee','2025-05-01 09:00','2025-05-03 10:00','Completed',true),(2,2,'Dr. Lee','2025-05-01 10:00','2025-05-20 14:00','No Show',false),
(3,3,'Dr. Shah','2025-05-02 08:00','2025-05-02 15:00','Completed',false),(4,4,'Dr. Shah','2025-05-03 11:00','2025-05-18 09:00','No Show',true),
(5,5,'Dr. Gomez','2025-05-04 12:00','2025-05-08 11:00','Completed',true),(6,6,'Dr. Gomez','2025-05-05 09:00','2025-05-30 16:00','No Show',false),
(7,1,'Dr. Lee','2025-05-10 09:00','2025-05-12 10:00','Completed',true),(8,7,'Dr. Shah','2025-05-11 08:00','2025-05-25 13:00','Canceled',true),
(9,8,'Dr. Gomez','2025-05-12 14:00','2025-05-13 09:00','Completed',false),(10,9,'Dr. Lee','2025-05-15 09:00','2025-06-10 15:00','No Show',false),
(11,10,'Dr. Shah','2025-05-20 09:00','2025-05-23 10:00','Completed',true),(12,11,'Dr. Gomez','2025-05-22 09:00','2025-06-05 11:00','Completed',true);

CREATE VIEW appointment_features AS
SELECT *,EXTRACT(EPOCH FROM(appointment_at-scheduled_at))/86400.0 lead_days,
 TRIM(to_char(appointment_at,'Day')) appointment_weekday,(status='No Show') no_show
FROM appointments WHERE status IN('Completed','No Show');

-- Overall KPI.
SELECT COUNT(*) scheduled_visits,COUNT(*) FILTER(WHERE no_show) no_shows,ROUND(100.0*AVG(no_show::int),1) no_show_pct FROM appointment_features;

-- Lead-time relationship.
SELECT CASE WHEN lead_days<=1 THEN '0-1 days' WHEN lead_days<=7 THEN '2-7 days' WHEN lead_days<=14 THEN '8-14 days' ELSE '15+ days' END lead_time_band,
 COUNT(*) appointments,ROUND(100.0*AVG(no_show::int),1) no_show_pct
FROM appointment_features GROUP BY 1 ORDER BY MIN(lead_days);

-- Reminder and provider scorecards.
SELECT sms_reminder,COUNT(*) appointments,ROUND(100.0*AVG(no_show::int),1) no_show_pct FROM appointment_features GROUP BY sms_reminder ORDER BY sms_reminder DESC;
SELECT provider,COUNT(*) appointments,ROUND(100.0*AVG(no_show::int),1) no_show_pct,ROUND(AVG(lead_days)::numeric,1) avg_lead_days
FROM appointment_features GROUP BY provider ORDER BY no_show_pct DESC;
SELECT appointment_weekday,COUNT(*) appointments,ROUND(100.0*AVG(no_show::int),1) no_show_pct
FROM appointment_features GROUP BY appointment_weekday ORDER BY no_show_pct DESC;

