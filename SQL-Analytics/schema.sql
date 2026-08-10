-- ============================================================
--  BPO Contact-Centre Analytics — Database Schema (SQLite)
--  Author: Neo Mamabolo
--  A small star-style model: campaigns & agents (dimensions)
--  with a calls fact table. All sample data is synthetic.
-- ============================================================

DROP TABLE IF EXISTS calls;
DROP TABLE IF EXISTS agents;
DROP TABLE IF EXISTS campaigns;

-- Dimension: client campaigns run by the BPO
CREATE TABLE campaigns (
    campaign_id    INTEGER PRIMARY KEY,
    campaign_name  TEXT    NOT NULL,
    client         TEXT    NOT NULL,
    campaign_type  TEXT    NOT NULL      -- Sales | Collections | Retentions | Customer Care | Tech Support | Lead Gen
);

-- Dimension: agents, with HR attributes for attrition analysis
CREATE TABLE agents (
    agent_id       INTEGER PRIMARY KEY,
    full_name      TEXT    NOT NULL,
    gender         TEXT,                 -- Female | Male
    team           TEXT,
    campaign_id    INTEGER NOT NULL REFERENCES campaigns(campaign_id),
    hire_date      TEXT    NOT NULL,     -- ISO date
    status         TEXT    NOT NULL,     -- Active | Resigned
    exit_date      TEXT,                 -- ISO date, NULL while Active
    monthly_salary REAL
);

-- Fact: one row per handled/abandoned call
CREATE TABLE calls (
    call_id         INTEGER PRIMARY KEY,
    campaign_id     INTEGER NOT NULL REFERENCES campaigns(campaign_id),
    agent_id        INTEGER          REFERENCES agents(agent_id),  -- NULL when abandoned in queue
    call_date       TEXT    NOT NULL,
    handle_time_sec INTEGER,           -- 0 when abandoned
    wait_time_sec   INTEGER,           -- time in queue before answer/abandon
    answered        INTEGER NOT NULL,  -- 1 = answered, 0 = abandoned
    csat            INTEGER,           -- 1-5 survey score, NULL if not surveyed
    resolved        INTEGER,           -- 1 = first-contact resolved, 0 = not, NULL if abandoned
    sale_amount     REAL DEFAULT 0     -- revenue booked on the call (0 if none)
);

CREATE INDEX idx_calls_campaign ON calls(campaign_id);
CREATE INDEX idx_calls_agent    ON calls(agent_id);
CREATE INDEX idx_calls_date     ON calls(call_date);
