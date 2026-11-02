"""ClinicFlow: appointment scheduling and patient records API with object-level access control."""
from datetime import date, datetime, time, timedelta
from pathlib import Path

from flask import g, jsonify, request

from .core import Resource, audit, db, err, make_app, now, require, tx, validate

ROOT = Path(__file__).resolve().parent.parent
ROLES = ("admin", "doctor", "receptionist", "patient")
DEFAULT_ROLE = "patient"
FRONT_DESK = ("admin", "receptionist")
MY_PATIENT = "(SELECT id FROM patients WHERE user_id=?)"


def appt_scope(u):
    if u["role"] == "patient":
        return f"t.patient_id={MY_PATIENT}", [u["id"]]
    if u["role"] == "doctor":
        return "t.doctor_id=?", [u["id"]]


def rx_scope(u):
    if u["role"] == "patient":
        return f"t.appointment_id IN (SELECT id FROM appointments WHERE patient_id={MY_PATIENT})", [u["id"]]
    if u["role"] == "doctor":
        return "t.appointment_id IN (SELECT id FROM appointments WHERE doctor_id=?)", [u["id"]]


def patient_scope(u):
    if u["role"] == "patient":
        return "t.user_id=?", [u["id"]]
    if u["role"] == "doctor":
        return "t.id IN (SELECT patient_id FROM appointments WHERE doctor_id=?)", [u["id"]]


def conflict(c, doctor_id, patient_id, start, end):
    r = c.execute("SELECT doctor_id FROM appointments WHERE status='scheduled' AND (doctor_id=? OR patient_id=?) AND starts_at<? AND ends_at>?",
                  (doctor_id, patient_id, end, start)).fetchone()
    if r:
        err(409, "slot_unavailable", "The doctor is already booked at that time" if r["doctor_id"] == doctor_id else "The patient already has an appointment at that time")


def own_appointment(appointment_id):
    """Doctors may only attach notes/prescriptions to their own, non-cancelled appointments."""
    a = db().execute("SELECT doctor_id, status FROM appointments WHERE id=?", (appointment_id,)).fetchone()
    if not a or a["doctor_id"] != g.user["id"]:
        err(403, "forbidden", "You can only add records to your own appointments")
    if a["status"] == "cancelled":
        err(409, "conflict", "The appointment was cancelled")


def create_app(config=None):
    def on_register(c, uid, d):
        c.execute("INSERT INTO patients(user_id, full_name) VALUES(?,?)", (uid, d["name"]))

    app = make_app(ROOT, roles=ROLES, default_role=DEFAULT_ROLE, directory_roles=("doctor",), on_register=on_register, config=config)

    def dob_ok(c, e=None):
        if c.get("date_of_birth") and c["date_of_birth"] > date.today().isoformat():
            err(422, "validation_error", "Validation failed", {"date_of_birth": "Cannot be in the future"})

    Resource("patients", "patients", {"full_name": {"required": True, "max": 120}, "date_of_birth": {"type": "date"},
             "phone": {"max": 20, "pattern": r"\+?[0-9 ()-]{7,20}", "pattern_msg": "Enter a valid phone number"}},
             read=("admin", "receptionist", "doctor", "patient"), write=FRONT_DESK, delete=("admin",), search=("t.full_name", "t.phone"),
             sortable={"full_name": "t.full_name", "created_at": "t.id"}, scope=patient_scope, audit_reads=True,
             hook_create=dob_ok, hook_update=dob_ok).register(app)

    appts = Resource("appointments", "appointments", {}, allow=("list", "get"), scope=appt_scope, search=("p.full_name", "d.name", "t.reason"),
                     filters=("status", "doctor_id"), default_sort="t.starts_at DESC", sortable={"starts_at": "t.starts_at"},
                     select="t.*, p.full_name AS patient_name, d.name AS doctor_name",
                     joins="JOIN patients p ON p.id=t.patient_id JOIN users d ON d.id=t.doctor_id")
    appts.register(app)

    @app.post("/api/appointments")
    @require("admin", "receptionist", "patient")
    def book():
        d = validate({"patient_id": {"type": "int", "fk": "patients"}, "doctor_id": {"type": "int", "required": True},
                      "starts_at": {"type": "datetime", "required": True}, "duration_minutes": {"type": "int", "required": True, "min": 15, "max": 120},
                      "reason": {"max": 300}}, request.get_json(silent=True))
        if d["duration_minutes"] % 15:
            err(422, "validation_error", "Validation failed", {"duration_minutes": "Must be a multiple of 15"})
        if g.user["role"] == "patient":
            row = db().execute("SELECT id FROM patients WHERE user_id=?", (g.user["id"],)).fetchone()
            if not row:
                err(409, "conflict", "No patient record is linked to your account")
            d["patient_id"] = row["id"]
        elif not d.get("patient_id"):
            err(422, "validation_error", "Validation failed", {"patient_id": "Required"})
        if not db().execute("SELECT 1 FROM users WHERE id=? AND role='doctor' AND active=1", (d["doctor_id"],)).fetchone():
            err(422, "validation_error", "Validation failed", {"doctor_id": "Select a valid doctor"})
        start = datetime.fromisoformat(d["starts_at"])
        end = start + timedelta(minutes=d["duration_minutes"])
        if start.weekday() > 4 or start.time() < time(8) or end.date() != start.date() or end.time() > time(18):
            err(422, "validation_error", "Validation failed", {"starts_at": "Clinic hours are Monday to Friday, 08:00 to 18:00"})
        if start <= datetime.now():
            err(422, "validation_error", "Validation failed", {"starts_at": "Must be in the future"})
        s, e = start.strftime("%Y-%m-%dT%H:%M"), end.strftime("%Y-%m-%dT%H:%M")
        with tx() as c:
            conflict(c, d["doctor_id"], d["patient_id"], s, e)
            aid = c.execute("INSERT INTO appointments(patient_id,doctor_id,starts_at,ends_at,reason,created_by) VALUES(?,?,?,?,?,?)",
                            (d["patient_id"], d["doctor_id"], s, e, d.get("reason"), g.user["id"])).lastrowid
            audit("create", "appointments", aid)
        return jsonify(data=appts._one(aid, scoped=False)), 201

    @app.post("/api/appointments/<int:aid>/cancel")
    @require("admin", "receptionist", "patient")
    def cancel(aid):
        a = appts._one(aid)  # scoped: patients can only reach their own
        if a["status"] != "scheduled":
            err(409, "conflict", f"A {a['status']} appointment cannot be cancelled")
        if g.user["role"] == "patient" and a["starts_at"] <= datetime.now().strftime("%Y-%m-%dT%H:%M"):
            err(409, "conflict", "Past appointments cannot be cancelled")
        with tx() as c:
            c.execute("UPDATE appointments SET status='cancelled' WHERE id=?", (aid,))
            audit("cancel", "appointments", aid)
        return jsonify(data=appts._one(aid))

    @app.post("/api/appointments/<int:aid>/status")
    @require("admin", "doctor")
    def set_status(aid):
        d = validate({"status": {"type": "enum", "choices": ["completed", "no_show"], "required": True}}, request.get_json(silent=True))
        a = appts._one(aid)  # doctors are scoped to their own appointments
        if a["status"] != "scheduled":
            err(409, "conflict", f"A {a['status']} appointment cannot be updated")
        with tx() as c:
            c.execute("UPDATE appointments SET status=? WHERE id=?", (d["status"], aid))
            audit(d["status"], "appointments", aid)
        return jsonify(data=appts._one(aid))

    def note_create(c):
        own_appointment(c["appointment_id"])
        c["doctor_id"] = g.user["id"]

    def note_update(c, e):
        c.pop("appointment_id", None)
        c["updated_at"] = now()

    Resource("visit-notes", "visit_notes", {"appointment_id": {"type": "int", "required": True, "fk": "appointments"}, "diagnosis": {"max": 500}, "notes": {"max": 4000}},
             read=("admin", "doctor"), write=("doctor",), allow=("list", "get", "create", "update"), scope=lambda u: ("t.doctor_id=?", [u["id"]]) if u["role"] == "doctor" else None,
             audit_reads=True, hook_create=note_create, hook_update=note_update, search=("p.full_name", "t.diagnosis"),
             select="t.*, p.full_name AS patient_name, a.starts_at",
             joins="JOIN appointments a ON a.id=t.appointment_id JOIN patients p ON p.id=a.patient_id").register(app)

    Resource("prescriptions", "prescriptions", {"appointment_id": {"type": "int", "required": True, "fk": "appointments"}, "medication": {"required": True, "max": 120},
             "dosage": {"required": True, "max": 120}, "instructions": {"max": 500}}, read=("admin", "doctor", "patient"), write=("doctor",),
             allow=("list", "get", "create"), scope=rx_scope, hook_create=lambda c: own_appointment(c["appointment_id"]), search=("t.medication", "p.full_name"),
             select="t.*, p.full_name AS patient_name, a.starts_at",
             joins="JOIN appointments a ON a.id=t.appointment_id JOIN patients p ON p.id=a.patient_id").register(app)

    @app.get("/api/stats")
    @require()
    def stats():
        f, a = appt_scope(g.user) or ("1=1", [])
        q = lambda extra, *args: db().execute(f"SELECT COUNT(*) FROM appointments t WHERE {f} AND {extra}", [*a, *args]).fetchone()[0]
        today, nowm = date.today().isoformat(), datetime.now().strftime("%Y-%m-%dT%H:%M")
        cards = [{"label": "Today's appointments", "value": q("t.status IN ('scheduled','completed') AND substr(t.starts_at,1,10)=?", today)},
                 {"label": "Upcoming", "value": q("t.status='scheduled' AND t.starts_at>=?", nowm)},
                 {"label": "Completed", "value": q("t.status='completed'")}]
        if g.user["role"] in ("admin", "receptionist"):
            cards.append({"label": "Registered patients", "value": db().execute("SELECT COUNT(*) FROM patients").fetchone()[0]})
        st = {r["status"]: r["n"] for r in db().execute(f"SELECT status, COUNT(*) n FROM appointments t WHERE {f} GROUP BY status", a)}
        return jsonify(data={"cards": cards, "breakdowns": [{"title": "Appointments by status", "items": [{"label": s, "value": st.get(s, 0)} for s in ("scheduled", "completed", "cancelled", "no_show")]}]})

    return app
