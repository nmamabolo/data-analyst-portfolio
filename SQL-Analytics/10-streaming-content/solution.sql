-- Streaming Content Analytics | PostgreSQL 13+
DROP SCHEMA IF EXISTS portfolio_10 CASCADE;
CREATE SCHEMA portfolio_10;
SET search_path TO portfolio_10;

CREATE TABLE titles (title_id INT PRIMARY KEY, title_name TEXT, genre TEXT, duration_minutes INT);
CREATE TABLE views (view_id INT PRIMARY KEY, user_id INT, title_id INT REFERENCES titles, started_at TIMESTAMP, minutes_watched INT);
INSERT INTO titles VALUES (1,'Orbit','Sci-Fi',50),(2,'Deep Space','Sci-Fi',45),(3,'Kitchen Rush','Reality',40),(4,'Final Plate','Reality',55),(5,'Hidden Truth','Drama',60),(6,'City Lights','Drama',48);
INSERT INTO views VALUES
(1,101,1,'2025-06-01 19:00',50),(2,101,2,'2025-06-01 19:55',43),(3,101,5,'2025-06-02 20:00',25),
(4,102,3,'2025-06-01 18:00',40),(5,102,4,'2025-06-01 18:45',50),(6,103,5,'2025-06-03 21:00',60),
(7,103,6,'2025-06-04 21:00',48),(8,104,1,'2025-06-04 10:00',20),(9,104,2,'2025-06-04 10:25',15),
(10,105,3,'2025-06-05 17:00',38),(11,105,3,'2025-06-06 17:00',40),(12,106,6,'2025-06-06 20:00',46);

CREATE VIEW view_metrics AS
SELECT v.*,t.title_name,t.genre,t.duration_minutes,
 LEAST(100.0*v.minutes_watched/NULLIF(t.duration_minutes,0),100) completion_pct,
 (v.minutes_watched>=.9*t.duration_minutes) completed
FROM views v JOIN titles t USING(title_id);

-- Genre engagement.
SELECT genre,COUNT(*) views,COUNT(DISTINCT user_id) unique_viewers,
 ROUND(SUM(minutes_watched)/60.0,1) watch_hours,ROUND(AVG(completion_pct),1) avg_completion_pct,
 ROUND(100.0*AVG(completed::int),1) completed_view_pct
FROM view_metrics GROUP BY genre ORDER BY watch_hours DESC;

-- Best title inside every genre.
WITH title_kpis AS (
 SELECT genre,title_name,COUNT(*) views,ROUND(AVG(completion_pct),1) avg_completion_pct,SUM(minutes_watched) minutes_watched
 FROM view_metrics GROUP BY genre,title_name
), ranked AS (
 SELECT *,DENSE_RANK() OVER(PARTITION BY genre ORDER BY minutes_watched DESC,avg_completion_pct DESC) genre_rank FROM title_kpis
)
SELECT * FROM ranked WHERE genre_rank<=2 ORDER BY genre,genre_rank;

-- Sessionize viewing: a gap over 30 minutes starts a new session.
WITH ordered AS (
 SELECT v.*,LAG(started_at+minutes_watched*interval '1 minute') OVER(PARTITION BY user_id ORDER BY started_at) prior_end FROM views v
), marked AS (
 SELECT *,CASE WHEN prior_end IS NULL OR started_at-prior_end>interval '30 minutes' THEN 1 ELSE 0 END new_session FROM ordered
), numbered AS (
 SELECT *,SUM(new_session) OVER(PARTITION BY user_id ORDER BY started_at) session_id FROM marked
)
SELECT user_id,session_id,MIN(started_at) session_start,COUNT(*) titles_started,SUM(minutes_watched) minutes_watched,
 (COUNT(*)>=2 AND SUM(minutes_watched)>=80) binge_session
FROM numbered GROUP BY user_id,session_id ORDER BY user_id,session_start;

