# Test report (authoring environment)

Command: `python -m unittest discover -s tests -t . -v`  
Environment: Python 3.12.3, Flask 3.1.3, SQLite 3.45.1

Overall: Ran 39 tests in 15.031s OK

| Test | Result |
|---|---|
| `test_core.AuthTests.test_bad_credentials_are_indistinguishable` | PASS |
| `test_core.AuthTests.test_duplicate_email_case_insensitive` | PASS |
| `test_core.AuthTests.test_health` | PASS |
| `test_core.AuthTests.test_logout_revokes_token` | PASS |
| `test_core.AuthTests.test_protected_requires_valid_token` | PASS |
| `test_core.AuthTests.test_rate_limit_on_login` | PASS |
| `test_core.AuthTests.test_register_login_me` | PASS |
| `test_core.AuthTests.test_register_validation` | PASS |
| `test_core.HardeningTests.test_cors_allowlist` | PASS |
| `test_core.HardeningTests.test_errors_are_json_and_do_not_leak` | PASS |
| `test_core.HardeningTests.test_pagination_and_bad_params` | PASS |
| `test_core.HardeningTests.test_passwords_stored_hashed` | PASS |
| `test_core.HardeningTests.test_production_requires_strong_secret` | PASS |
| `test_core.HardeningTests.test_security_headers` | PASS |
| `test_core.HardeningTests.test_sql_injection_attempts_are_inert` | PASS |
| `test_core.HardeningTests.test_static_frontend_and_path_traversal` | PASS |
| `test_core.UserAdminTests.test_admin_cannot_demote_or_disable_self` | PASS |
| `test_core.UserAdminTests.test_audit_log_records_events_and_hides_secrets` | PASS |
| `test_core.UserAdminTests.test_deactivated_user_loses_access_and_login` | PASS |
| `test_core.UserAdminTests.test_non_admin_forbidden` | PASS |
| `test_core.UserAdminTests.test_reset_password` | PASS |
| `test_core.UserAdminTests.test_role_change_applies_immediately_and_validates` | PASS |
| `test_domain.BookingTests.test_cancel_frees_slot_and_status_rules` | PASS |
| `test_domain.BookingTests.test_concurrent_bookings_for_one_slot` | PASS |
| `test_domain.BookingTests.test_database_trigger_blocks_overlap_even_if_app_check_is_bypassed` | PASS |
| `test_domain.BookingTests.test_doctors_see_and_update_only_their_own` | PASS |
| `test_domain.BookingTests.test_double_booking_prevented_for_doctor_and_patient` | PASS |
| `test_domain.BookingTests.test_patient_books_for_self_and_cannot_spoof_patient_id` | PASS |
| `test_domain.BookingTests.test_patient_cannot_touch_other_patients_appointments` | PASS |
| `test_domain.BookingTests.test_validation_rules` | PASS |
| `test_domain.PatientTests.test_doctor_sees_only_patients_they_treat` | PASS |
| `test_domain.PatientTests.test_patient_sees_only_own_record` | PASS |
| `test_domain.PatientTests.test_reads_of_patient_records_are_logged` | PASS |
| `test_domain.PatientTests.test_registration_creates_linked_patient_record` | PASS |
| `test_domain.PatientTests.test_write_rbac_and_validation` | PASS |
| `test_domain.RecordTests.test_cannot_attach_records_to_cancelled_or_foreign_appointments` | PASS |
| `test_domain.RecordTests.test_prescriptions_visible_only_to_own_patient_and_doctor` | PASS |
| `test_domain.RecordTests.test_visit_notes_access_control` | PASS |
| `test_domain.StatsTests.test_stats_are_scoped_by_role` | PASS |

Failures found and fixed during development are listed in the delivery notes; nothing here is marked PASS without having been executed.
