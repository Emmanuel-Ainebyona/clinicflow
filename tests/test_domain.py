import sqlite3
import threading
from datetime import date, datetime, timedelta

from app.seed import next_weekday
from tests.base import ADMIN, Base

DOC1, DOC2, REC, PAT = "doctor@demo.test", "doctor2@demo.test", "reception@demo.test", "patient@demo.test"
NEWPAT = {"email": "walkin@example.test", "name": "Walk In", "password": "Str0ng-Passw0rd"}


class Clinic(Base):
    def uid(self, email):
        return self.data(self.get("/api/auth/me", email), 200)["id"]

    def slot(self, days=14, hhmm="09:00"):
        return f"{next_weekday(days).isoformat()}T{hhmm}"

    def book(self, user, doctor, starts_at, minutes=30, **extra):
        return self.post("/api/appointments", user, json={"doctor_id": self.uid(doctor), "starts_at": starts_at, "duration_minutes": minutes, "reason": "Test", **extra})

    def my_patient(self, email=PAT):
        return self.data(self.get("/api/patients", email), 200)[0]


class PatientTests(Clinic):
    def test_registration_creates_linked_patient_record(self):
        self.post("/api/auth/register", json=NEWPAT)
        tok = self.data(self.login(NEWPAT["email"], NEWPAT["password"]), 200)["token"]
        rows = self.data(self.get("/api/patients", headers={"Authorization": "Bearer " + tok}), 200)
        self.assertEqual([r["full_name"] for r in rows], ["Walk In"])

    def test_patient_sees_only_own_record(self):
        rows = self.data(self.get("/api/patients?per_page=100", PAT), 200)
        self.assertEqual(len(rows), 1)
        others = self.data(self.get("/api/patients?per_page=100", REC), 200)
        other_id = next(p["id"] for p in others if p["id"] != rows[0]["id"])
        self.assertEqual(self.get(f"/api/patients/{other_id}", PAT).status_code, 404)
        self.assertEqual(self.get(f"/api/patients/{rows[0]['id']}", PAT).status_code, 200)

    def test_doctor_sees_only_patients_they_treat(self):
        seen = {p["full_name"] for p in self.data(self.get("/api/patients?per_page=100", DOC1), 200)}
        everyone = {p["full_name"] for p in self.data(self.get("/api/patients?per_page=100", REC), 200)}
        self.assertTrue(seen and seen < everyone)

    def test_write_rbac_and_validation(self):
        body = {"full_name": "Test Person", "date_of_birth": "1980-01-01", "phone": "+256 700 111 222"}
        self.assertEqual(self.post("/api/patients", PAT, json=body).status_code, 403)
        self.assertEqual(self.post("/api/patients", DOC1, json=body).status_code, 403)
        pid = self.data(self.post("/api/patients", REC, json=body), 201)["id"]
        for bad in ({**body, "date_of_birth": (date.today() + timedelta(days=1)).isoformat()}, {**body, "phone": "call me"}, {**body, "full_name": ""}, {**body, "date_of_birth": "01/01/1980"}):
            self.assertEqual(self.post("/api/patients", REC, json=bad).status_code, 422, bad)
        self.assertEqual(self.delete(f"/api/patients/{pid}", REC).status_code, 403)
        self.assertEqual(self.delete(f"/api/patients/{pid}", ADMIN).status_code, 200)

    def test_reads_of_patient_records_are_logged(self):
        pid = self.my_patient()["id"]
        self.get(f"/api/patients/{pid}", PAT)
        rows = self.data(self.get("/api/audit?entity=patients&action=read", ADMIN), 200)
        self.assertTrue(any(r["entity_id"] == str(pid) and r["user_email"] == PAT for r in rows))


class BookingTests(Clinic):
    def test_patient_books_for_self_and_cannot_spoof_patient_id(self):
        other = next(p["id"] for p in self.data(self.get("/api/patients?per_page=100", REC), 200) if p["id"] != self.my_patient()["id"])
        a = self.data(self.book(PAT, DOC1, self.slot(), patient_id=other), 201)
        self.assertEqual(a["patient_id"], self.my_patient()["id"])
        self.assertEqual(a["ends_at"][-5:], "09:30")

    def test_validation_rules(self):
        sunday = next_weekday(14)
        while sunday.weekday() != 6:
            sunday += timedelta(days=1)
        past = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%dT09:00")
        cases = {"sunday": (f"{sunday}T10:00", 30), "too early": (self.slot(hhmm="07:30"), 30), "runs past close": (self.slot(hhmm="17:45"), 30), "past": (past, 30),
                 "bad duration": (self.slot(), 20), "too long": (self.slot(), 180), "garbage date": ("tomorrow", 30)}
        for name, (when, mins) in cases.items():
            self.assertEqual(self.book(PAT, DOC1, when, mins).status_code, 422, name)
        self.assertEqual(self.book(PAT, DOC1, self.slot(hhmm="17:30"), 30).status_code, 201)  # ends exactly at close
        self.assertEqual(self.post("/api/appointments", PAT, json={"doctor_id": self.uid(REC), "starts_at": self.slot(21), "duration_minutes": 30}).status_code, 422)  # not a doctor
        self.assertEqual(self.book(REC, DOC1, self.slot(22)).status_code, 422)  # staff must name a patient

    def test_double_booking_prevented_for_doctor_and_patient(self):
        self.assertEqual(self.book(PAT, DOC1, self.slot(), 60).status_code, 201)
        self.post("/api/auth/register", json=NEWPAT)
        tok = {"Authorization": "Bearer " + self.data(self.login(NEWPAT["email"], NEWPAT["password"]), 200)["token"]}
        mk = lambda doc, when, m=30: self.post("/api/appointments", headers=tok, json={"doctor_id": self.uid(doc), "starts_at": when, "duration_minutes": m})
        self.assertEqual(mk(DOC1, self.slot(hhmm="09:30")).status_code, 409)       # doctor busy (overlap inside)
        self.assertEqual(mk(DOC1, self.slot(hhmm="08:45")).status_code, 409)       # overlap at the start
        self.assertEqual(mk(DOC1, self.slot(hhmm="10:00")).status_code, 201)       # back-to-back is fine
        self.assertEqual(self.book(PAT, DOC2, self.slot(hhmm="09:15")).status_code, 409)  # patient already booked elsewhere
        self.assertEqual(self.book(PAT, DOC2, self.slot(hhmm="11:00")).status_code, 201)

    def test_cancel_frees_slot_and_status_rules(self):
        a = self.data(self.book(PAT, DOC1, self.slot()), 201)
        self.assertEqual(self.data(self.post(f"/api/appointments/{a['id']}/cancel", PAT), 200)["status"], "cancelled")
        self.assertEqual(self.post(f"/api/appointments/{a['id']}/cancel", PAT).status_code, 409)
        self.assertEqual(self.book(REC, DOC1, self.slot(), patient_id=self.my_patient()["id"]).status_code, 201)
        self.assertEqual(self.post(f"/api/appointments/{a['id']}/status", DOC1, json={"status": "completed"}).status_code, 409)

    def test_patient_cannot_touch_other_patients_appointments(self):
        mine = self.data(self.get("/api/appointments?per_page=100", PAT), 200)
        self.assertTrue(mine and all(a["patient_id"] == self.my_patient()["id"] for a in mine))
        theirs = next(a for a in self.data(self.get("/api/appointments?per_page=100&status=scheduled", REC), 200) if a["patient_id"] != self.my_patient()["id"])
        self.assertEqual(self.get(f"/api/appointments/{theirs['id']}", PAT).status_code, 404)
        self.assertEqual(self.post(f"/api/appointments/{theirs['id']}/cancel", PAT).status_code, 404)

    def test_doctors_see_and_update_only_their_own(self):
        mine = self.data(self.get("/api/appointments?per_page=100", DOC1), 200)
        self.assertTrue(mine and all(a["doctor_name"] == "Dr. Grace Okello" for a in mine))
        other = next(a for a in self.data(self.get("/api/appointments?status=scheduled", DOC2), 200))
        self.assertEqual(self.post(f"/api/appointments/{other['id']}/status", DOC1, json={"status": "completed"}).status_code, 404)
        self.assertEqual(self.data(self.post(f"/api/appointments/{other['id']}/status", DOC2, json={"status": "completed"}), 200)["status"], "completed")
        self.assertEqual(self.post(f"/api/appointments/{other['id']}/status", PAT, json={"status": "completed"}).status_code, 403)

    def test_database_trigger_blocks_overlap_even_if_app_check_is_bypassed(self):
        self.book(PAT, DOC1, self.slot(), 30)
        con = sqlite3.connect(self.app.config["DATABASE_PATH"])
        s = self.slot(hhmm="09:10")
        with self.assertRaises(sqlite3.IntegrityError):
            con.execute("INSERT INTO appointments(patient_id,doctor_id,starts_at,ends_at) VALUES(2,?, ?, ?)", (self.uid(DOC1), s, s[:-5] + "09:40"))

    def test_concurrent_bookings_for_one_slot(self):
        codes, did = [], self.uid(DOC1)
        patients = [p["id"] for p in self.data(self.get("/api/patients?per_page=100", REC), 200)][:4]
        tok = self.tok(REC)

        def attempt(pid):
            r = self.app.test_client().post("/api/appointments", headers={"Authorization": "Bearer " + tok},
                                            json={"patient_id": pid, "doctor_id": did, "starts_at": self.slot(30, "14:00"), "duration_minutes": 30})
            codes.append(r.status_code)
        ts = [threading.Thread(target=attempt, args=(p,)) for p in patients]
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertEqual(sorted(codes), [201, 409, 409, 409])


class RecordTests(Clinic):
    def my_appt(self, doctor):
        return next(a for a in self.data(self.get("/api/appointments?per_page=100&status=scheduled", doctor), 200))["id"]

    def test_visit_notes_access_control(self):
        aid = self.my_appt(DOC1)
        body = {"appointment_id": aid, "diagnosis": "Flu", "notes": "Rest"}
        for who, code in ((PAT, 403), (REC, 403), (ADMIN, 403), (DOC2, 403)):
            self.assertEqual(self.post("/api/visit-notes", who, json=body).status_code, code, who)
        nid = self.data(self.post("/api/visit-notes", DOC1, json=body), 201)["id"]
        self.assertEqual(self.post("/api/visit-notes", DOC1, json=body).status_code, 409)  # one note per visit
        self.assertEqual(self.get(f"/api/visit-notes/{nid}", DOC2).status_code, 404)
        self.assertEqual(self.get(f"/api/visit-notes/{nid}", PAT).status_code, 403)
        self.assertEqual(self.get(f"/api/visit-notes/{nid}", REC).status_code, 403)
        self.assertEqual(self.get(f"/api/visit-notes/{nid}", DOC1).status_code, 200)
        self.assertEqual(self.get(f"/api/visit-notes/{nid}", ADMIN).status_code, 200)
        self.assertEqual(self.put(f"/api/visit-notes/{nid}", ADMIN, json={"notes": "x"}).status_code, 403)
        self.assertEqual(self.data(self.put(f"/api/visit-notes/{nid}", DOC1, json={"notes": "Updated", "appointment_id": 1}), 200)["appointment_id"], aid)
        reads = self.data(self.get("/api/audit?action=read&entity=visit-notes", ADMIN), 200)
        self.assertTrue(any(r["user_email"] == DOC1 for r in reads) and any(r["user_email"] == ADMIN for r in reads))

    def test_prescriptions_visible_only_to_own_patient_and_doctor(self):
        aid = self.my_appt(DOC1)
        rx = {"appointment_id": aid, "medication": "Paracetamol 500mg", "dosage": "2 tablets every 6h"}
        self.assertEqual(self.post("/api/prescriptions", REC, json=rx).status_code, 403)
        self.assertEqual(self.post("/api/prescriptions", DOC2, json=rx).status_code, 403)
        self.assertEqual(self.post("/api/prescriptions", DOC1, json={**rx, "medication": ""}).status_code, 422)
        pid = self.data(self.post("/api/prescriptions", DOC1, json=rx), 201)["id"]
        appt_patient = self.data(self.get(f"/api/appointments/{aid}", DOC1), 200)["patient_name"]
        self.post("/api/auth/register", json=NEWPAT)
        stranger = {"Authorization": "Bearer " + self.data(self.login(NEWPAT["email"], NEWPAT["password"]), 200)["token"]}
        self.assertEqual(self.data(self.get("/api/prescriptions", headers=stranger), 200), [])
        self.assertEqual(self.get(f"/api/prescriptions/{pid}", headers=stranger).status_code, 404)
        if appt_patient == "Pat Patient":
            self.assertTrue(any(r["id"] == pid for r in self.data(self.get("/api/prescriptions", PAT), 200)))
        self.assertTrue(all(r["patient_name"] == "Pat Patient" for r in self.data(self.get("/api/prescriptions", PAT), 200)))

    def test_cannot_attach_records_to_cancelled_or_foreign_appointments(self):
        a = self.data(self.book(PAT, DOC1, self.slot(40)), 201)["id"]
        self.post(f"/api/appointments/{a}/cancel", PAT)
        self.assertEqual(self.post("/api/visit-notes", DOC1, json={"appointment_id": a, "notes": "x"}).status_code, 409)
        self.assertEqual(self.post("/api/visit-notes", DOC1, json={"appointment_id": 99999, "notes": "x"}).status_code, 422)


class StatsTests(Clinic):
    def test_stats_are_scoped_by_role(self):
        card = lambda user, label: next(c["value"] for c in self.data(self.get("/api/stats", user), 200)["cards"] if c["label"] == label)
        self.assertEqual(card(REC, "Registered patients"), 6)
        self.assertEqual(card(DOC1, "Completed"), 2)
        self.assertEqual(card(DOC2, "Completed"), 1)
        self.assertEqual(card(PAT, "Completed"), 1)  # the demo patient has one past visit
        self.assertNotIn("Registered patients", [c["label"] for c in self.data(self.get("/api/stats", PAT), 200)["cards"]])
