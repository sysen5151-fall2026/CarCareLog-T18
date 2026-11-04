"""Requirement-linked checks for the implemented F.2.2 manual path.

These checks cover selected behaviors, not full ASR/FCS system acceptance.
"""
import unittest
from datetime import date
from unittest.mock import patch
import test_app
from backend import function_f22 as f22


class FunctionalRequirementTests(unittest.TestCase):
    setUp = test_app.AppTests.setUp
    tearDown = test_app.AppTests.tearDown
    call = test_app.AppTests.call
    car = test_app.AppTests.car
    record = test_app.AppTests.record
    dashboard = test_app.AppTests.dashboard
    rule = test_app.AppTests.rule

    def test_SRD_1_4_1_2_manual_requested_operation(self):
        """SRD 1.4.1.2: The CarCareLog System shall process each accepted vehicle-service request according to its requested maintenance-information operation.

        End-to-end manual subset only: route, confirmed save, retrieved evidence and calculation.
        """
        car=self.car(mileage=52000);self.rule(car,km=8000,months=6)
        status,saved=self.record(car,service_date='2026-10-31',mileage=52000,cost='89.99')
        self.assertEqual(status,201)
        data=self.dashboard(car)
        self.assertEqual(data['total_cents'],8999)
        self.assertEqual((data['reminders'][0]['due_date'],data['reminders'][0]['due_mileage']),
                         ('2027-04-30',60000))
        self.assertEqual(data['reminders'][0]['record_id'],saved['id'])

    def test_ASR_1_4_1_route_existing_vehicle(self):
        """ASR 1.4.1: The Application Service shall Validate and Route Owner Requests.

        Checks the local routing subset; authenticated ownership remains open.
        """
        car = self.car()
        self.assertEqual(self.record(car)[0], 201)
        self.assertEqual(self.record(999999)[0], 404)
        self.assertEqual(self.record(car, operation="unknown")[0], 400)
        self.assertEqual(len(self.dashboard(car)["records"]), 1)

    def test_ASR_1_2_1_reject_unconfirmed_transaction(self):
        """ASR 1.2.1: The Application Service shall provide Confirmed service record to the Vehicle Record Store.

        Unconfirmed attempts must leave persisted history unchanged.
        """
        car = self.car()
        for confirmation in (False, None, "true", 1):
            self.assertEqual(self.record(car, owner_confirmed=confirmation)[0], 400)
        self.assertEqual(self.dashboard(car)["records"], [])

    def test_ASR_1_4_3_commit_then_return_record_id(self):
        """ASR 1.4.3: The Application Service shall Coordinate Confirmed Record Transactions.

        Check committed ID, exact cents and rejection of an unconfirmed edit.
        """
        car = self.car()
        status, stored = self.record(car, cost="89.99")
        self.assertEqual(status, 201)
        data = self.dashboard(car)
        self.assertEqual(data["records"][0]["id"], stored["id"])
        self.assertEqual(data["total_cents"], 8999)
        original = data["records"][0]
        self.assertEqual(self.call(f'/api/records/{stored["id"]}', "PUT",
            {**original, "cost": "99.99"})[0], 400)
        self.assertEqual(self.dashboard(car)["total_cents"], 8999)

    def test_ASR_1_4_4_or_thresholds_and_confirmed_source(self):
        """ASR 1.4.4: The Application Service shall Calculate Maintenance Summary and Reminders.

        Independent expected date, mileage and source; either due limit suffices.
        """
        records = [dict(id=4, service_date="2026-10-31", service_item="Oil change",
            mileage=52000, category="Maintenance", cost_cents=8999)]
        rules = [dict(service_item="Oil change", interval_km=8000, interval_months=6)]
        data = f22.calculate_maintenance_summary_and_reminders(records, rules,
            vehicle_context={"id": 1, "mileage": 52000}, as_of=date(2026, 11, 1))
        reminder = data["reminders"][0]
        self.assertEqual((reminder["due_date"], reminder["due_mileage"], reminder["record_id"]),
                         ("2027-04-30", 60000, 4))
        for mileage, day in [(60000, date(2026, 11, 1)), (52000, date(2027, 4, 30))]:
            result = f22.calculate_maintenance_summary_and_reminders(records, rules,
                vehicle_context={"id": 1, "mileage": mileage}, as_of=day)
            self.assertEqual(result["reminders"][0]["status"], "Due / overdue")

    def test_FCS_2_1_2_manual_path_independent_of_external_AI(self):
        """FCS.2.1.2: The Application Service shall allow authorized core record read and manual confirmed-record submission when the AI Model Runtime is unavailable.

        Four read/write cases; no claim about seven-day system availability.
        Exact native statement and source are retained in requirements-baseline.json.
        """
        # A synthesis contribution only. This does not measure availability uptime.
        car = self.car()
        with patch.object(f22, "coordinate_ai_requests_and_responses",
                          side_effect=RuntimeError("AI unavailable")) as ai:
            status, saved = self.record(car)
            self.assertEqual(status, 201)  # create
            row = self.dashboard(car)['records'][0]  # read
            self.assertEqual(row['id'],saved['id'])
            self.assertEqual(self.call(f"/api/records/{saved['id']}",'PUT',
                {**row,'cost':'90.00','owner_confirmed':True})[0],200)  # update
            self.assertEqual(self.dashboard(car)['total_cents'],9000)
            self.assertEqual(self.call(f"/api/records/{saved['id']}",'DELETE')[0],200)  # delete
            self.assertEqual(self.dashboard(car)['records'],[])
            ai.assert_not_called()

    def test_ASR_1_4_2_external_AI_boundary_explicitly_unimplemented(self):
        """ASR 1.4.2: The Application Service shall Coordinate AI Requests and Responses.

        Only explicit unavailable signaling is checked; this requirement remains open.
        """
        # This verifies honest failure signaling, not successful AI extraction.
        with self.assertRaises(NotImplementedError):
            f22.coordinate_ai_requests_and_responses({},
                configured_ai_service_contract_limits={},
                authorized_records_and_source_references=[])

    def test_ASR_1_1_8_request_input_rejects_missing_vehicle(self):
        """ASR 1.1.8: The Application Service shall accept Validated owner service request from the Web Interface.

        Check valid local input and missing/malformed vehicle identifiers without saving.
        """
        car=self.car()
        for bad in (None,True,0,'bad'):
            self.assertEqual(self.record(bad)[0],400)
        self.assertEqual(self.dashboard(car)['records'],[])
        self.assertEqual(self.record(car)[0],201)

    def test_ASR_1_1_4_rule_input_requires_source_and_real_interval(self):
        """ASR 1.1.4: The Application Service shall accept Referenced maintenance interval rules from the Vehicle Owner.

        Check interval and reference validation; no interval is invented when absent.
        """
        car=self.car();self.record(car)
        self.assertEqual(self.dashboard(car)['reminders'],[])
        self.assertEqual(self.rule(car,km=0,months=0)[0],400)
        self.assertEqual(self.call('/api/reminders','POST',dict(vehicle_id=car,
            service_item='Oil change',interval_km=5000,interval_months=6,reference=''))[0],400)
        self.assertEqual(self.rule(car)[0],200)
        self.assertEqual(self.dashboard(car)['reminders'][0]['reference'],"Test owner's manual, p. 12")

    def test_ASR_1_1_9_selected_vehicle_record_input(self):
        """ASR 1.1.9: The Application Service shall accept Authorized records and source references from the Vehicle Record Store.

        Selected-vehicle filtering only; the word Authorized is not an authentication claim.
        """
        first,second=self.car(),self.car('Second')
        self.record(first,provider='First');self.record(second,provider='Second')
        self.assertEqual([x['provider'] for x in self.dashboard(first)['records']],['First'])

    def test_ASR_1_1_1_stored_confirmation_matches_persisted_id(self):
        """ASR 1.1.1: The Application Service shall accept Stored record confirmation from the Vehicle Record Store.

        Successful acknowledgement must identify the independently retrieved stored record.
        """
        car=self.car();status,result=self.record(car)
        self.assertEqual(status,201);self.assertIsInstance(result['id'],int)
        self.assertEqual(self.dashboard(car)['records'][0]['id'],result['id'])

    def test_ASR_1_2_6_prepared_information_output(self):
        """ASR 1.2.6: The Application Service shall provide Prepared vehicle information to the Web Interface.

        Check the response contract, exact total, selected vehicle and source record.
        """
        car=self.car();_,saved=self.record(car,cost='89.99');self.rule(car)
        data=self.dashboard(car)
        self.assertTrue({'vehicle','records','reminders','total_cents','monthly'}<=set(data))
        self.assertEqual(data['vehicle']['id'],car)
        self.assertEqual(data['total_cents'],8999)
        self.assertEqual(data['reminders'][0]['record_id'],saved['id'])

    def test_ASR_1_3_1_internal_record_store_roundtrip(self):
        """ASR 1.3.1: The Application Service shall interface with the Vehicle Record Store through the Application Service / Vehicle Record Store.

        Internal route DTO is passed unchanged to confirmation and then retrieved.
        """
        car=self.car()
        raw=dict(vehicle_id=car,operation='create_record',service_date=date.today().isoformat(),
            service_item='Oil change',category='Maintenance',mileage=10000,cost='89.99',
            provider='Contract fixture',notes='',owner_confirmed=True)
        status,routed=self.call('/internal/v1/validate-and-route','POST',raw)
        self.assertEqual(status,200);self.assertEqual(self.dashboard(car)['records'],[])
        self.assertEqual(self.call('/internal/v1/confirmed-transaction','POST',
            {**routed,'owner_confirmed':False})[0],400)
        status,saved=self.call('/internal/v1/confirmed-transaction','POST',routed)
        self.assertEqual(status,201)
        status,data=self.call('/internal/v1/prepare-information','POST',{'vehicle_id':car})
        self.assertEqual(status,200);self.assertEqual(data['total_cents'],8999)
        self.assertEqual(data['records'][0]['id'],saved['id'])
        self.assertEqual(data['records'][0]['provider'],'Contract fixture')

    def test_ASR_1_3_2_web_interface_output_matches_internal_summary(self):
        """ASR 1.3.2: The Application Service shall interface with the Web Interface through the Web Interface / Application Service.

        Public web and internal contract adapters expose the same prepared information.
        """
        car=self.car();self.record(car);self.rule(car)
        status,internal=self.call('/internal/v1/prepare-information','POST',{'vehicle_id':car})
        self.assertEqual(status,200);self.assertEqual(internal,self.dashboard(car))

    def test_ASR_1_1_7_ai_unavailable_is_explicit_without_write(self):
        """ASR 1.1.7: The Application Service shall accept Evidence-backed answer or AI failure response from the AI Model Runtime.

        Only local unavailable response is covered; external runtime integration remains open.
        """
        car=self.car()
        status,result=self.call('/internal/v1/coordinate-ai','POST',{'vehicle_id':car,'kind':'receipt'})
        self.assertEqual(status,503);self.assertEqual(result['status'],'unavailable')
        self.assertIsNone(result['proposal']);self.assertEqual(self.dashboard(car)['records'],[])

    def test_UC2_update_reload_restore_preserves_ledger_and_other_vehicle(self):
        """UC.2 / ASR 1.4.4: saved rule changes calculations, not service history.

        API-level integration evidence with a fixed observation date; not a browser,
        authenticated owner-isolation, or full requirement-acceptance test.
        """
        class ObservationDate(date):
            @classmethod
            def today(cls):
                return cls(2026, 11, 3)

        with patch.object(test_app.app, 'date', ObservationDate):
            car, other = self.car(mileage=52000), self.car('Other vehicle')
            self.rule(car, km=8000, months=6)
            self.rule(other, km=5000, months=6)
            for service, amount, mileage in [('Oil change', '79.99', 44000),
                                             ('Tire rotation', '35.00', 48000),
                                             ('Brake service', '245.00', 51500)]:
                self.assertEqual(self.record(car, service_item=service, cost=amount,
                    mileage=mileage, service_date='2026-10-01')[0], 201)
            status, saved = self.record(car, cost='89.99', mileage=52000,
                                       service_date='2026-10-31')
            self.assertEqual(status, 201)
            before, other_before = self.dashboard(car), self.dashboard(other)
            self.assertEqual((len(before['records']), before['total_cents']), (4, 44998))
            original_rule = before['reminders'][0]
            self.assertEqual((original_rule['due_mileage'], original_rule['due_date'],
                              original_rule['status']), (60000, '2027-04-30', 'Scheduled'))
            self.assertEqual(self.rule(car, km=1000, months=1)[0], 200)
            changed = self.dashboard(car)  # fresh HTTP GET and SQLite connection
            rule = changed['reminders'][0]
            self.assertEqual((rule['due_mileage'], rule['due_date'], rule['status'],
                              rule['record_id']), (53000, '2026-11-30', 'Upcoming', saved['id']))
            self.assertEqual((rule['interval_km'], rule['interval_months'], rule['reference']),
                             (1000, 1, "Test owner's manual, p. 12"))
            self.assertEqual(changed['records'], before['records'])
            self.assertEqual(changed['total_cents'], before['total_cents'])
            self.assertEqual(self.dashboard(other), other_before)
            self.assertEqual(self.rule(car, km=8000, months=6)[0], 200)
            restored = self.dashboard(car)
            self.assertEqual(restored['reminders'], before['reminders'])
            self.assertEqual(restored['records'], before['records'])
            self.assertEqual(restored['total_cents'], before['total_cents'])

    def test_UC2_invalid_update_preserves_saved_rule(self):
        """UC.2: rejected configuration leaves the last valid rule and ledger intact."""
        car = self.car()
        self.record(car)
        self.rule(car, km=8000, months=6)
        before = self.dashboard(car)
        for changes in [dict(interval_km=0, interval_months=0),
                        dict(reference=''), dict(interval_km=-1)]:
            request = dict(vehicle_id=car, service_item='Oil change', interval_km=1000,
                           interval_months=1, reference='Classroom test reference')
            request.update(changes)
            self.assertEqual(self.call('/api/reminders', 'POST', request)[0], 400)
            self.assertEqual(self.dashboard(car), before)

    def test_UC2_repeated_save_keeps_one_rule_and_same_service_records(self):
        """UC.2: repeated saves update one rule rather than duplicating it or events."""
        car = self.car()
        self.record(car)
        before = self.dashboard(car)
        for _ in range(3):
            self.assertEqual(self.rule(car, km=1000, months=1)[0], 200)
        after = self.dashboard(car)
        self.assertEqual(len(after['reminders']), 1)
        self.assertEqual(after['records'], before['records'])
        self.assertEqual(after['total_cents'], before['total_cents'])

    def test_SR08_upcoming_distance_uses_500_miles_in_km(self):
        """SR08: CarCareLog shall display the upcoming or overdue status of each configured maintenance item for the selected vehicle.

        Baseline parameter: 30 days OR 500 international miles = 804.672 km.
        Test below, exactly at and above the distance window with time out of range.
        """
        records=[dict(id=1,service_date='2026-01-01',service_item='Oil change',
            mileage=10000,category='Maintenance',cost_cents=100)]
        rules=[dict(service_item='Oil change',interval_km=5000,interval_months=12)]
        for remaining,expected in [(804.671,'Upcoming'),(804.672,'Upcoming'),(804.673,'Scheduled')]:
            data=f22.calculate_maintenance_summary_and_reminders(records,rules,
                vehicle_context={'mileage':15000-remaining},as_of=date(2026,1,1))
            self.assertEqual(data['reminders'][0]['status'],expected)

    def test_SR08_upcoming_time_uses_30_day_inclusive_window(self):
        """SR08: CarCareLog shall display the upcoming or overdue status of each configured maintenance item for the selected vehicle.

        Independent time cases: 31 days scheduled, 30 days upcoming, zero days due.
        """
        records=[dict(id=1,service_date='2026-01-01',service_item='Oil change',
            mileage=10000,category='Maintenance',cost_cents=100)]
        rules=[dict(service_item='Oil change',interval_km=5000,interval_months=1)]
        for day,expected in [(date(2026,1,1),'Scheduled'),(date(2026,1,2),'Upcoming'),(date(2026,2,1),'Due / overdue')]:
            data=f22.calculate_maintenance_summary_and_reminders(records,rules,
                vehicle_context={'mileage':10000},as_of=day)
            self.assertEqual(data['reminders'][0]['status'],expected)


if __name__ == "__main__":
    unittest.main()
