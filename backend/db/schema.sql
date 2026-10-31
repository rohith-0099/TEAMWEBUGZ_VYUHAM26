CREATE EXTENSION IF NOT EXISTS vector;

-- reports / analyses (P3)
CREATE TABLE IF NOT EXISTS analyses (
  id            TEXT PRIMARY KEY,
  title         TEXT NOT NULL DEFAULT '',
  source_url    TEXT,
  published_at  TIMESTAMPTZ,
  status        TEXT NOT NULL DEFAULT 'running',     -- running | done | error
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  result        JSONB NOT NULL DEFAULT '{}'::jsonb    -- full ReportAnalysis JSON
);

CREATE TABLE IF NOT EXISTS feedback (
  id           SERIAL PRIMARY KEY,
  analysis_id  TEXT REFERENCES analyses(id) ON DELETE CASCADE,
  target_type  TEXT NOT NULL CHECK (target_type IN ('technique','ioc')),
  target_id    TEXT NOT NULL,
  verdict      TEXT NOT NULL CHECK (verdict IN ('accept','reject')),
  note         TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ATT&CK v20 (P4 fills)
CREATE TABLE IF NOT EXISTS attack_tactics (
  tactic_id  TEXT PRIMARY KEY,        -- "TA0001"
  shortname  TEXT UNIQUE NOT NULL,    -- "initial-access"
  name       TEXT NOT NULL,
  ord        INT NOT NULL             -- matrix order, 0..14
);
CREATE TABLE IF NOT EXISTS attack_techniques (
  technique_id     TEXT PRIMARY KEY,  -- "T1059.001"
  stix_id          TEXT UNIQUE NOT NULL,
  name             TEXT NOT NULL,
  description      TEXT NOT NULL,
  tactics          TEXT[] NOT NULL,   -- tactic shortnames
  is_subtechnique  BOOLEAN NOT NULL,
  parent_id        TEXT,
  platforms        TEXT[],
  url              TEXT,
  embedding        vector(384)
);
CREATE INDEX IF NOT EXISTS attack_techniques_emb ON attack_techniques USING hnsw (embedding vector_cosine_ops);
CREATE TABLE IF NOT EXISTS attack_examples (   -- procedure examples, extra retrieval text
  id            SERIAL PRIMARY KEY,
  technique_id  TEXT NOT NULL REFERENCES attack_techniques(technique_id),
  text          TEXT NOT NULL,
  embedding     vector(384)
);
CREATE INDEX IF NOT EXISTS attack_examples_emb ON attack_examples USING hnsw (embedding vector_cosine_ops);
CREATE TABLE IF NOT EXISTS attack_objects (    -- every STIX object, raw (strategies, analytics, groups, mitigations, deprecated...)
  stix_id    TEXT PRIMARY KEY,
  attack_id  TEXT,                    -- external ATT&CK id if any
  type       TEXT NOT NULL,
  name       TEXT,
  deprecated BOOLEAN NOT NULL DEFAULT false,
  revoked    BOOLEAN NOT NULL DEFAULT false,
  data       JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS attack_objects_aid ON attack_objects(attack_id);
CREATE INDEX IF NOT EXISTS attack_objects_type ON attack_objects(type);
CREATE TABLE IF NOT EXISTS attack_relationships (
  id                 TEXT PRIMARY KEY,
  source_ref         TEXT NOT NULL,
  target_ref         TEXT NOT NULL,
  relationship_type  TEXT NOT NULL,
  description        TEXT
);
CREATE INDEX IF NOT EXISTS attack_rel_src ON attack_relationships(source_ref);
CREATE INDEX IF NOT EXISTS attack_rel_tgt ON attack_relationships(target_ref);

-- temporal memory graph (P5 writes)
CREATE TABLE IF NOT EXISTS mem_nodes (
  id          TEXT PRIMARY KEY,       -- "ioc:domain:evil.com", "technique:T1059", "actor:apt29"
  type        TEXT NOT NULL,          -- ioc | technique | actor | malware | report | sector
  key         TEXT NOT NULL,
  display     TEXT NOT NULL,
  first_seen  TIMESTAMPTZ,
  last_seen   TIMESTAMPTZ,
  UNIQUE (type, key)
);
CREATE TABLE IF NOT EXISTS mem_edges (
  id          SERIAL PRIMARY KEY,
  src         TEXT NOT NULL REFERENCES mem_nodes(id),
  dst         TEXT NOT NULL REFERENCES mem_nodes(id),
  relation    TEXT NOT NULL,          -- mentioned_in | uses | attributed_to | targets | indicates
  valid_from  TIMESTAMPTZ,
  valid_to    TIMESTAMPTZ,
  report_id   TEXT REFERENCES analyses(id) ON DELETE CASCADE,
  evidence    JSONB
);

-- evaluation (P5)
CREATE TABLE IF NOT EXISTS eval_runs (
  id       SERIAL PRIMARY KEY,
  ran_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  payload  JSONB NOT NULL               -- EvalResponse (see §8)
);

-- LLM response cache (P5)
CREATE TABLE IF NOT EXISTS llm_cache (
  key         TEXT PRIMARY KEY,
  response    JSONB NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- external lookups (NVD, CISA KEV), cached so a demo works offline and we respect rate limits
CREATE TABLE IF NOT EXISTS ext_cache (
  key         TEXT PRIMARY KEY,           -- "kev:feed" | "nvd:CVE-2024-4577"
  payload     JSONB NOT NULL,
  fetched_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
