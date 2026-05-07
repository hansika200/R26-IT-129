-- ============================================================
-- schema.sql
-- SQLite schema for Hansika Teacher Dashboard
-- SLSL Recognition System — Objective 4
-- ============================================================
-- All tables use CREATE TABLE IF NOT EXISTS so this is safe
-- to run on every application startup (idempotent).
-- ============================================================

PRAGMA foreign_keys = ON;

-- ── Users ────────────────────────────────────────────────────────────────────
-- Stores both teachers and admins. Role controls access.
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT    NOT NULL UNIQUE,
    email           TEXT    NOT NULL UNIQUE,
    password_hash   TEXT    NOT NULL,
    role            TEXT    NOT NULL DEFAULT 'teacher',   -- 'teacher' | 'admin'
    full_name       TEXT,
    is_active       INTEGER NOT NULL DEFAULT 1,           -- 1=active, 0=disabled
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ── Signs (vocabulary) ───────────────────────────────────────────────────────
-- A sign is a gesture with a label submitted by a teacher.
-- Status lifecycle: pending → approved | rejected
CREATE TABLE IF NOT EXISTS signs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    label           TEXT    NOT NULL,                     -- e.g. "hello", "thank you"
    description     TEXT,
    video_path      TEXT,                                 -- stored in storage/teacher_recordings/
    keypoints_path  TEXT,                                 -- extracted .npy file path
    submitted_by    INTEGER NOT NULL REFERENCES users(id),
    status          TEXT    NOT NULL DEFAULT 'pending',   -- 'pending' | 'approved' | 'rejected'
    sample_count    INTEGER NOT NULL DEFAULT 0,           -- number of keypoint samples
    is_in_model     INTEGER NOT NULL DEFAULT 0,           -- 1 = included in active TFLite model
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ── Peer Reviews ─────────────────────────────────────────────────────────────
-- Teacher A submits a sign; Teacher B reviews it.
CREATE TABLE IF NOT EXISTS peer_reviews (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    sign_id         INTEGER NOT NULL REFERENCES signs(id) ON DELETE CASCADE,
    reviewer_id     INTEGER NOT NULL REFERENCES users(id),
    decision        TEXT    NOT NULL,                     -- 'approved' | 'rejected'
    rejection_reason TEXT,
    notes           TEXT,
    reviewed_at     TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ── Student Recordings ───────────────────────────────────────────────────────
-- Recordings made by students during practice sessions.
CREATE TABLE IF NOT EXISTS student_recordings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id      TEXT    NOT NULL,                     -- student identifier (from Flutter app)
    sign_label      TEXT    NOT NULL,                     -- intended sign label
    video_path      TEXT,
    keypoints_path  TEXT,
    prediction      TEXT,                                 -- what the model predicted
    confidence      REAL,                                 -- model confidence (0–1)
    is_annotated    INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ── Annotations ──────────────────────────────────────────────────────────────
-- Teacher annotation of a student recording.
-- Annotated data feeds back into the training pipeline.
CREATE TABLE IF NOT EXISTS annotations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    recording_id    INTEGER NOT NULL REFERENCES student_recordings(id) ON DELETE CASCADE,
    annotated_by    INTEGER NOT NULL REFERENCES users(id),
    is_correct      INTEGER NOT NULL,                     -- 1=correct, 0=incorrect
    correct_label   TEXT,                                 -- teacher's correction label
    notes           TEXT,
    included_in_dataset INTEGER NOT NULL DEFAULT 0,       -- 1 = exported to training data
    annotated_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ── Assignments ───────────────────────────────────────────────────────────────
-- Teachers create assignments linking a set of signs to a student group.
CREATE TABLE IF NOT EXISTS assignments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT    NOT NULL,
    description     TEXT,
    created_by      INTEGER NOT NULL REFERENCES users(id),
    sign_labels     TEXT    NOT NULL,                     -- JSON array of sign labels
    due_date        TEXT,
    is_active       INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ── Student Progress ─────────────────────────────────────────────────────────
-- Tracks how each student performs on each assignment.
CREATE TABLE IF NOT EXISTS student_progress (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id      TEXT    NOT NULL,
    assignment_id   INTEGER NOT NULL REFERENCES assignments(id) ON DELETE CASCADE,
    signs_attempted TEXT,                                 -- JSON array
    signs_correct   TEXT,                                 -- JSON array
    score           REAL    NOT NULL DEFAULT 0.0,         -- 0–100
    completion_pct  REAL    NOT NULL DEFAULT 0.0,         -- 0–100
    last_activity   TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(student_id, assignment_id)
);

-- ── Retraining Logs ──────────────────────────────────────────────────────────
-- Each row records one retraining event.
CREATE TABLE IF NOT EXISTS retraining_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    triggered_by    INTEGER REFERENCES users(id),
    trigger_reason  TEXT    NOT NULL,                     -- 'manual' | 'auto_threshold'
    new_signs       TEXT,                                 -- JSON: labels of newly added signs
    sample_count    INTEGER,
    status          TEXT    NOT NULL DEFAULT 'pending',   -- 'pending' | 'running' | 'success' | 'failed'
    model_path      TEXT,                                 -- path to newly exported .tflite
    error_message   TEXT,
    started_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    finished_at     TEXT
);

-- ── Indexes ───────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_signs_status       ON signs(status);
CREATE INDEX IF NOT EXISTS idx_signs_label        ON signs(label);
CREATE INDEX IF NOT EXISTS idx_reviews_sign       ON peer_reviews(sign_id);
CREATE INDEX IF NOT EXISTS idx_annotations_rec    ON annotations(recording_id);
CREATE INDEX IF NOT EXISTS idx_progress_student   ON student_progress(student_id);
CREATE INDEX IF NOT EXISTS idx_retrain_status     ON retraining_logs(status);
