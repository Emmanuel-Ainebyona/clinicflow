"""Demo seed data (fictional; local development only)."""
from datetime import date, datetime, timedelta

from . import ROOT
from .core import connect, migrate, seed_users

USERS = [("admin@demo.test", "Ada Admin", "admin"), ("doctor@demo.test", "Dr. Grace Okello", "doctor"), ("doctor2@demo.test", "Dr. Ben Nankya", "doctor"),
         ("reception@demo.test", "Rita Reception", "receptionist"), ("patient@demo.test", "Pat Patient", "patient")]
PATIENTS = [("Joan Mukasa", "1985-04-12", "+256 700 000 101"), ("David Ssemwogerere", "1972-11-03", "+256 700 000 102"), ("Esther Achieng", "1999-07-21", "+256 700 000 103"),
            ("Moses Kato", "1990-01-30", "+256 700 000 104"), ("Lillian Nabirye", "1964-09-09", "+256 700 000 105")]


def next_weekday(days_ahead):
    d = date.today() + timedelta(days=days_ahead)
    while d.weekday() > 4:
        d += timedelta(days=1)
    return d


def seed(db_path):
    migrate(db_path, ROOT / "migrations")
    c = connect(db_path)
    c.execute("BEGIN")
    if not seed_users(c, USERS):
        c.execute("ROLLBACK")
        return False
    uid = {r[1]: r[0] for r in c.execute("SELECT id,email FROM users")}
    c.execute("INSERT INTO patients(user_id, full_name, date_of_birth) VALUES(?,?,?)", (uid["patient@demo.test"], "Pat Patient", "1995-05-05"))
    for p in PATIENTS:
        c.execute("INSERT INTO patients(full_name,date_of_birth,phone) VALUES(?,?,?)", p)
    pid = [r[0] for r in c.execute("SELECT id FROM patients ORDER BY id")]
    d1, d2, rec = uid["doctor@demo.test"], uid["doctor2@demo.test"], uid["reception@demo.test"]

    def appt(patient, doctor, when, hhmm, mins, reason, status):
        s = datetime.fromisoformat(f"{when.isoformat()}T{hhmm}")
        return c.execute("INSERT INTO appointments(patient_id,doctor_id,starts_at,ends_at,reason,status,created_by) VALUES(?,?,?,?,?,?,?)",
                         (patient, doctor, s.strftime("%Y-%m-%dT%H:%M"), (s + timedelta(minutes=mins)).strftime("%Y-%m-%dT%H:%M"), reason, status, rec)).lastrowid
    done = [appt(pid[0], d1, next_weekday(-20), "09:00", 30, "Persistent cough", "completed"), appt(pid[2], d1, next_weekday(-12), "10:30", 30, "Annual check-up", "completed"),
            appt(pid[1], d2, next_weekday(-8), "14:00", 45, "Back pain follow-up", "completed")]
    appt(pid[3], d2, next_weekday(-5), "11:00", 30, "Skin rash", "no_show")
    appt(pid[4], d1, next_weekday(-3), "15:00", 30, "Blood pressure review", "cancelled")
    c.execute("INSERT INTO visit_notes(appointment_id,doctor_id,diagnosis,notes) VALUES(?,?,?,?)", (done[0], d1, "Acute bronchitis", "Chest clear on auscultation. Advised rest and fluids."))
    c.execute("INSERT INTO visit_notes(appointment_id,doctor_id,diagnosis,notes) VALUES(?,?,?,?)", (done[1], d1, "Healthy", "Routine screening normal."))
    c.execute("INSERT INTO prescriptions(appointment_id,medication,dosage,instructions) VALUES(?,?,?,?)", (done[0], "Amoxicillin 500mg", "1 capsule three times daily", "Take for 5 days after food."))
    appt(pid[0], d1, next_weekday(2), "09:00", 30, "Cough follow-up", "scheduled")
    appt(pid[5], d1, next_weekday(2), "09:30", 30, "Vaccination consult", "scheduled")
    appt(pid[1], d2, next_weekday(3), "13:00", 45, "Physiotherapy referral", "scheduled")
    appt(pid[2], d2, next_weekday(4), "10:00", 30, "Lab results discussion", "scheduled")
    c.execute("COMMIT")
    c.close()
    return True
