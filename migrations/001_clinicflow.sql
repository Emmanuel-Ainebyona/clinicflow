CREATE TABLE patients(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER UNIQUE REFERENCES users(id) ON DELETE SET NULL,
  full_name TEXT NOT NULL,
  date_of_birth TEXT,
  phone TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE appointments(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,
  doctor_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  starts_at TEXT NOT NULL, ends_at TEXT NOT NULL,
  reason TEXT,
  status TEXT NOT NULL DEFAULT 'scheduled' CHECK (status IN ('scheduled','completed','cancelled','no_show')),
  created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  CHECK (ends_at > starts_at)
);
CREATE INDEX idx_appt_doctor ON appointments(doctor_id, starts_at);
CREATE INDEX idx_appt_patient ON appointments(patient_id, starts_at);
-- Database-level backstop: no double booking of a doctor or a patient, even under concurrent writers.
CREATE TRIGGER appt_no_overlap_insert BEFORE INSERT ON appointments WHEN NEW.status = 'scheduled'
BEGIN
  SELECT RAISE(ABORT, 'overlapping appointment') WHERE EXISTS (
    SELECT 1 FROM appointments a WHERE a.status = 'scheduled' AND (a.doctor_id = NEW.doctor_id OR a.patient_id = NEW.patient_id)
      AND a.starts_at < NEW.ends_at AND a.ends_at > NEW.starts_at);
END;
CREATE TRIGGER appt_no_overlap_update BEFORE UPDATE ON appointments WHEN NEW.status = 'scheduled'
BEGIN
  SELECT RAISE(ABORT, 'overlapping appointment') WHERE EXISTS (
    SELECT 1 FROM appointments a WHERE a.id <> NEW.id AND a.status = 'scheduled' AND (a.doctor_id = NEW.doctor_id OR a.patient_id = NEW.patient_id)
      AND a.starts_at < NEW.ends_at AND a.ends_at > NEW.starts_at);
END;
CREATE TABLE visit_notes(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  appointment_id INTEGER NOT NULL UNIQUE REFERENCES appointments(id) ON DELETE RESTRICT,
  doctor_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  diagnosis TEXT, notes TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')), updated_at TEXT
);
CREATE TABLE prescriptions(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  appointment_id INTEGER NOT NULL REFERENCES appointments(id) ON DELETE RESTRICT,
  medication TEXT NOT NULL, dosage TEXT NOT NULL, instructions TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_rx_appt ON prescriptions(appointment_id);
