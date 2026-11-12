import os
import tempfile
import unittest
from datetime import date, timedelta
from werkzeug.security import check_password_hash
from app import create_app
from database import init_db, get_db, close_db
from seed import seed_database
from services.auth_service import register_user, authenticate_user, get_user_by_id
from services.community_service import (
    create_community, join_community_by_code, is_member, is_community_admin,
    get_community_stats
)
from services.loan_service import create_loan_request, accept_loan_request, acknowledge_loan_agreement, sync_overdue_loans
from services.repayment_service import record_repayment, calculate_outstanding_balance, generate_simulated_reference
from services.analytics_service import export_table_to_csv, get_analytics_data

class MukoLendComprehensiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_directory = tempfile.TemporaryDirectory()
        cls.test_db = os.path.join(cls.test_directory.name, "test_mukolend.db")

        cls.app = create_app({
            'TESTING': True,
            'WTF_CSRF_ENABLED': False,
            'DATABASE_PATH': cls.test_db,
            'SECRET_KEY': 'test-secret-key-1234'
        })

        with cls.app.app_context():
            init_db(cls.test_db)
            seed_database(cls.test_db)

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            close_db()
        cls.test_directory.cleanup()

    def setUp(self):
        self.client = self.app.test_client()

    def set_user(self, user_id, role='user'):
        with self.client.session_transaction() as session:
            session['user_id'] = user_id
            session['user_role'] = role

    # -------------------------------------------------------------
    # 1. USER AUTHENTICATION TESTS
    # -------------------------------------------------------------
    def test_user_registration_and_password_hashing(self):
        with self.app.app_context():
            user_id, errors = register_user(
                full_name="Kuda Sithole",
                email="kuda.test@mukolend.co.zw",
                password="SecurePassword123!",
                confirm_password="SecurePassword123!"
            )
            self.assertIsNotNone(user_id, "User registration should return a user ID")
            self.assertEqual(len(errors), 0)

            # Verify password is not plain text and hashed properly
            user = get_user_by_id(user_id)
            self.assertNotEqual(user['password_hash'], "SecurePassword123!")
            self.assertTrue(check_password_hash(user['password_hash'], "SecurePassword123!"))

    def test_duplicate_email_registration_rejected(self):
        with self.app.app_context():
            user_id, errors = register_user(
                full_name="Duplicate Farai",
                email="farai@mukolend.co.zw",  # Already seeded in database
                password="SecurePassword123!",
                confirm_password="SecurePassword123!"
            )
            self.assertIsNone(user_id)
            self.assertTrue(any("already exists" in e.lower() for e in errors))

    def test_authenticate_user_success_and_failure(self):
        with self.app.app_context():
            # Valid credentials (Admin)
            user, error = authenticate_user("admin@mukolend.co.zw", "admin12345")
            self.assertIsNotNone(user)
            self.assertIsNone(error)
            self.assertEqual(user['role'], 'admin')

            # Invalid password
            user_bad, error_bad = authenticate_user("admin@mukolend.co.zw", "WrongPassword!")
            self.assertIsNone(user_bad)
            self.assertIn("Invalid email or password", error_bad)

    # -------------------------------------------------------------
    # 2. COMMUNITY MANAGEMENT & CODE GENERATION TESTS
    # -------------------------------------------------------------
    def test_create_community_and_unique_code(self):
        with self.app.app_context():
            comm_id, error = create_community(
                name="Bulawayo Innovators Circle",
                description="Community credit circle for tech entrepreneurs",
                creator_id=1
            )
            self.assertIsNotNone(comm_id)
            self.assertIsNone(error)

            conn = get_db()
            comm = conn.execute("SELECT * FROM communities WHERE id = ?", (comm_id,)).fetchone()
            self.assertTrue(comm['invite_code'].startswith("MUKO-"))
            self.assertEqual(len(comm['invite_code']), 15)  # MUKO- plus 10 random characters

            # Creator must be admin
            self.assertTrue(is_community_admin(comm_id, 1))
            self.assertTrue(is_member(comm_id, 1))

    def test_join_community_duplicate_rejection(self):
        with self.app.app_context():
            conn = get_db()
            comm = conn.execute("SELECT * FROM communities WHERE id = 1").fetchone()
            invite_code = comm['invite_code']

            # User 1 is creator of community 1, should reject duplicate
            comm_id, err = join_community_by_code(invite_code, 1)
            self.assertIn("already a member", err.lower())

    def test_community_group_workflow_and_authorization(self):
        self.set_user(1)
        list_response = self.client.get('/communities')
        self.assertEqual(list_response.status_code, 200)
        self.assertIn(b'Harare Central Small Traders Mukando', list_response.data)

        create_page = self.client.get('/communities/create')
        self.assertEqual(create_page.status_code, 200)
        import re
        token_match = re.search(rb'name="submission_token" value="([^"]+)"', create_page.data)
        self.assertIsNotNone(token_match)
        create_token = token_match.group(1).decode()

        invalid_create = self.client.post('/communities/create', data={
            'name': '  ', 'description': 'Not valid',
            'submission_token': create_token
        })
        self.assertEqual(invalid_create.status_code, 200)
        self.assertIn(b'at least 3 characters', invalid_create.data)

        created = self.client.post('/communities/create', data={
            'name': 'Mbare Market Circle',
            'description': 'Peer lending group for local market traders.',
            'submission_token': create_token
        }, follow_redirects=True)
        self.assertEqual(created.status_code, 200)
        self.assertIn(b'Mbare Market Circle', created.data)
        with self.app.app_context():
            conn = get_db()
            community = conn.execute(
                "SELECT * FROM communities WHERE name = ?", ('Mbare Market Circle',)
            ).fetchone()
            self.assertIsNotNone(community)
            community_id = community['id']
            invite_code = community['invite_code']
            self.assertEqual(len(invite_code), 15)
            self.assertTrue(is_community_admin(community_id, 1))
            self.assertTrue(is_member(community_id, 1))

        duplicate_create = self.client.post('/communities/create', data={
            'name': 'Mbare Market Circle',
            'description': 'Peer lending group for local market traders.',
            'submission_token': create_token
        }, follow_redirects=True)
        self.assertEqual(duplicate_create.status_code, 200)
        with self.app.app_context():
            self.assertEqual(
                get_db().execute(
                    "SELECT COUNT(*) FROM communities WHERE name = ?", ('Mbare Market Circle',)
                ).fetchone()[0],
                1
            )

        not_found = self.client.get('/communities/999999')
        self.assertEqual(not_found.status_code, 404)

        self.set_user(2)
        preview = self.client.get(f'/communities/{community_id}')
        self.assertEqual(preview.status_code, 200)
        self.assertIn(b'Enter Invite Code', preview.data)
        self.assertNotIn(invite_code.encode(), preview.data)
        self.assertNotIn(b'Member Roster', preview.data)

        invalid_join = self.client.post('/communities/join', data={'invite_code': 'MUKO-NOT-VALID'})
        self.assertEqual(invalid_join.status_code, 302)
        self.set_user(4)
        joined = self.client.post('/communities/join', data={'invite_code': invite_code}, follow_redirects=True)
        self.assertEqual(joined.status_code, 200)
        self.assertIn(b'Mbare Market Circle', joined.data)
        repeated_join = self.client.post('/communities/join', data={'invite_code': invite_code}, follow_redirects=True)
        self.assertEqual(repeated_join.status_code, 200)
        with self.app.app_context():
            conn = get_db()
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) FROM community_members WHERE community_id = ? AND user_id = ?",
                    (community_id, 4)
                ).fetchone()[0],
                1
            )

        self.set_user(6)
        self.client.post('/communities/join', data={'invite_code': invite_code})
        with self.app.app_context():
            self.assertTrue(is_member(community_id, 6))

        unauthorized_edit = self.client.post(f'/communities/{community_id}/edit', data={
            'name': 'Unauthorized Edit', 'description': ''
        }, follow_redirects=True)
        self.assertIn(b'Only a community administrator', unauthorized_edit.data)

        self.set_user(1)
        updated = self.client.post(f'/communities/{community_id}/edit', data={
            'name': 'Mbare Traders Circle', 'description': 'Updated group description.'
        }, follow_redirects=True)
        self.assertEqual(updated.status_code, 200)
        self.assertIn(b'Mbare Traders Circle', updated.data)

        with self.app.app_context():
            due_date = (date.today() + timedelta(days=20)).isoformat()
            request_id, error = create_loan_request(
                community_id=community_id,
                borrower_id=1,
                amount_cents=10000,
                currency='USD',
                reason='Purchase market stall inventory',
                proposed_due_date=due_date
            )
            self.assertIsNone(error)
            loan_id, error = accept_loan_request(request_id, 4)
            self.assertIsNone(error)
            success, _ = acknowledge_loan_agreement(loan_id, 1)
            self.assertTrue(success)
            payment_success, _ = record_repayment(
                loan_id, 2500, 'GROUP-WORKFLOW-PARTIAL', 1, date.today().isoformat()
            )
            self.assertTrue(payment_success)
            stats = get_community_stats(community_id)
            self.assertEqual(stats['total_members'], 3)
            self.assertEqual(stats['active_loans'], 1)
            self.assertEqual(stats['outstanding_minor'], 7500)
            self.assertEqual(stats['repaid_volume_minor'], 2500)

        self.set_user(6)
        restricted_loan = self.client.get(f'/loans/{loan_id}')
        self.assertEqual(restricted_loan.status_code, 302)
        permitted_leave = self.client.post(
            f'/communities/{community_id}/leave', follow_redirects=True
        )
        self.assertIn(b'You have left the community', permitted_leave.data)
        with self.app.app_context():
            self.assertFalse(is_member(community_id, 6))

        self.set_user(5)
        self.client.post('/communities/join', data={'invite_code': invite_code})
        self.set_user(1)
        removed_member = self.client.post(
            f'/communities/{community_id}/members/5/remove', follow_redirects=True
        )
        self.assertEqual(removed_member.status_code, 200)
        with self.app.app_context():
            self.assertFalse(is_member(community_id, 5))

        self.set_user(1)
        details_after_repayment = self.client.get(f'/communities/{community_id}')
        self.assertEqual(details_after_repayment.status_code, 200)
        self.assertIn(b'$75.00', details_after_repayment.data)
        self.assertIn(b'Community Loan Activity', details_after_repayment.data)

        self.set_user(4)
        leave_with_loan = self.client.post(f'/communities/{community_id}/leave', follow_redirects=True)
        self.assertIn(b'unsettled loans', leave_with_loan.data)
        regenerated_as_member = self.client.post(
            f'/communities/{community_id}/invite-code/regenerate', follow_redirects=True
        )
        self.assertIn(b'Only a community administrator', regenerated_as_member.data)

        self.set_user(1)
        last_admin_leave = self.client.post(f'/communities/{community_id}/leave', follow_redirects=True)
        self.assertIn(b'last administrator cannot leave', last_admin_leave.data)
        transferred = self.client.post(
            f'/communities/{community_id}/admin/transfer',
            data={'new_admin_id': '4'},
            follow_redirects=True
        )
        self.assertIn(b'Administrator privileges transferred', transferred.data)
        with self.app.app_context():
            self.assertFalse(is_community_admin(community_id, 1))
            self.assertTrue(is_community_admin(community_id, 4))

        self.set_user(4)
        regenerated = self.client.post(
            f'/communities/{community_id}/invite-code/regenerate', follow_redirects=True
        )
        self.assertIn(b'A new invitation code has been generated', regenerated.data)
        with self.app.app_context():
            new_code = get_db().execute(
                "SELECT invite_code FROM communities WHERE id = ?", (community_id,)
            ).fetchone()['invite_code']
        self.assertNotEqual(new_code, invite_code)

    # -------------------------------------------------------------
    # 3. LOAN REQUEST LIFECYCLE TESTS (MINOR UNITS IN CENTS)
    # -------------------------------------------------------------
    def test_loan_request_creation_and_validation(self):
        with self.app.app_context():
            tomorrow = (date.today() + timedelta(days=14)).isoformat()
            
            # Valid request: $120.00 (12000 minor units)
            req_id, err = create_loan_request(
                community_id=1,
                borrower_id=2, # User 2 is member of community 1
                amount_cents=12000,
                currency="USD",
                reason="Stocking up agro supplies",
                proposed_due_date=tomorrow
            )
            self.assertIsNotNone(req_id)
            self.assertIsNone(err)

            conn = get_db()
            req = conn.execute("SELECT * FROM loan_requests WHERE id = ?", (req_id,)).fetchone()
            self.assertEqual(req['amount_minor'], 12000)
            self.assertEqual(req['status'], 'pending')

    def test_request_agreement_and_repayment_routes_keep_database_consistent(self):
        due_date = (date.today() + timedelta(days=30)).isoformat()
        self.set_user(2)

        invalid = self.client.post('/requests/create', data={
            'community_id': '1',
            'amount': '0',
            'currency': 'USD',
            'reason': 'Valid reason for request',
            'proposed_due_date': due_date
        })
        self.assertEqual(invalid.status_code, 200)
        self.assertIn(b'Invalid loan amount', invalid.data)

        request_response = self.client.post('/requests/create', data={
            'community_id': '1',
            'amount': '25.00',
            'currency': 'USD',
            'reason': 'Stock for the weekend market',
            'proposed_due_date': due_date
        }, follow_redirects=True)
        self.assertEqual(request_response.status_code, 200)
        self.assertIn(b'Loan request submitted successfully', request_response.data)
        self.assertIn(b'Pending', request_response.data)
        request_list = self.client.get('/requests')
        self.assertEqual(request_list.status_code, 200)
        self.assertIn(b'Stock for the weekend market', request_list.data)

        with self.app.app_context():
            conn = get_db()
            request_row = conn.execute("""
                SELECT * FROM loan_requests
                WHERE borrower_id = 2 AND amount_minor = 2500
                ORDER BY id DESC LIMIT 1
            """).fetchone()
            self.assertIsNotNone(request_row)
            self.assertEqual(request_row['status'], 'pending')
            request_id = request_row['id']

        self.set_user(1)
        accepted = self.client.post(
            f'/requests/{request_id}/accept',
            data={'agreed_fee': '0.50'},
            follow_redirects=True
        )
        self.assertEqual(accepted.status_code, 200)
        self.assertIn(b'Peer-to-Peer Community Loan Agreement', accepted.data)

        with self.app.app_context():
            conn = get_db()
            request_row = conn.execute(
                "SELECT status FROM loan_requests WHERE id = ?", (request_id,)
            ).fetchone()
            loan = conn.execute(
                "SELECT * FROM loans WHERE request_id = ?", (request_id,)
            ).fetchone()
            self.assertEqual(request_row['status'], 'accepted')
            self.assertEqual(loan['status'], 'awaiting_agreement')
            self.assertEqual(loan['principal_minor'], 2500)
            self.assertEqual(loan['fee_minor'], 50)
            loan_id = loan['id']

        repeated_accept = self.client.post(
            f'/requests/{request_id}/accept',
            data={'agreed_fee': '0.50'}
        )
        self.assertEqual(repeated_accept.status_code, 302)
        with self.app.app_context():
            self.assertEqual(
                get_db().execute("SELECT COUNT(*) FROM loans WHERE request_id = ?", (request_id,)).fetchone()[0],
                1
            )

        self.set_user(2)
        agreement = self.client.get(f'/loans/{loan_id}/agreement')
        self.assertEqual(agreement.status_code, 200)
        self.assertIn(b'Acknowledge & Sign Agreement', agreement.data)
        activated = self.client.post(f'/loans/{loan_id}/acknowledge', follow_redirects=True)
        self.assertEqual(activated.status_code, 200)
        self.assertIn(b'Active', activated.data)

        repayment_form = self.client.get(f'/loans/{loan_id}/repay')
        self.assertEqual(repayment_form.status_code, 200)
        self.assertIn(b'name="simulated_reference"', repayment_form.data)
        self.assertIn(b'name="repayment_date"', repayment_form.data)
        self.assertIn(b'$25.50', repayment_form.data)

        zero_payment = self.client.post(f'/loans/{loan_id}/repay', data={
            'amount': '0',
            'simulated_reference': 'ROUTE-ZERO',
            'repayment_date': date.today().isoformat()
        })
        self.assertEqual(zero_payment.status_code, 200)
        self.assertIn(b'Invalid payment amount', zero_payment.data)

        partial = self.client.post(f'/loans/{loan_id}/repay', data={
            'amount': '10.00',
            'simulated_reference': 'ROUTE-PARTIAL',
            'repayment_date': date.today().isoformat()
        }, follow_redirects=True)
        self.assertEqual(partial.status_code, 200)
        self.assertIn(b'ROUTE-PARTIAL', partial.data)
        self.assertIn(b'$15.50', partial.data)

        with self.app.app_context():
            conn = get_db()
            before_invalid_payments = conn.execute(
                "SELECT COUNT(*) FROM repayments WHERE loan_id = ?", (loan_id,)
            ).fetchone()[0]
            self.assertEqual(calculate_outstanding_balance(loan_id)[4], 1550)

        for amount, reference in (('15.51', 'ROUTE-OVERPAY'), ('10.00', 'ROUTE-PARTIAL')):
            rejected = self.client.post(f'/loans/{loan_id}/repay', data={
                'amount': amount,
                'simulated_reference': reference,
                'repayment_date': date.today().isoformat()
            })
            self.assertEqual(rejected.status_code, 200)
            with self.app.app_context():
                conn = get_db()
                self.assertEqual(
                    conn.execute("SELECT COUNT(*) FROM repayments WHERE loan_id = ?", (loan_id,)).fetchone()[0],
                    before_invalid_payments
                )
                self.assertEqual(calculate_outstanding_balance(loan_id)[4], 1550)

        self.set_user(4)
        unauthorized = self.client.post(f'/loans/{loan_id}/repay', data={
            'amount': '1.00',
            'simulated_reference': 'ROUTE-UNAUTHORIZED',
            'repayment_date': date.today().isoformat()
        })
        self.assertEqual(unauthorized.status_code, 302)
        with self.app.app_context():
            conn = get_db()
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM repayments WHERE loan_id = ?", (loan_id,)).fetchone()[0],
                before_invalid_payments
            )
        self.assertEqual(self.client.get('/analytics/export/users').status_code, 302)

        self.set_user(2)
        final_payment = self.client.post(f'/loans/{loan_id}/repay', data={
            'amount': '15.50',
            'simulated_reference': 'ROUTE-FINAL',
            'repayment_date': date.today().isoformat()
        }, follow_redirects=True)
        self.assertEqual(final_payment.status_code, 200)
        self.assertIn(b'ROUTE-FINAL', final_payment.data)

        with self.app.app_context():
            conn = get_db()
            loan = conn.execute("SELECT status FROM loans WHERE id = ?", (loan_id,)).fetchone()
            self.assertEqual(loan['status'], 'repaid')
            self.assertEqual(calculate_outstanding_balance(loan_id)[3:], (2550, 0))
            all_kpis, _, _ = get_analytics_data()
            active_kpis, _, _ = get_analytics_data(status_filter='active')
            self.assertEqual(all_kpis['total_loan_requests'], active_kpis['total_loan_requests'])
            self.assertGreaterEqual(all_kpis['total_requested_minor'], 2500)

        dashboard = self.client.get('/dashboard')
        self.assertEqual(dashboard.status_code, 200)
        self.assertIn(b'My Loan Requests', dashboard.data)
        self.assertIn(b'Principal borrowed:', dashboard.data)

        repayment_ledger = self.client.get('/repayments')
        self.assertEqual(repayment_ledger.status_code, 200)
        self.assertIn(b'ROUTE-FINAL', repayment_ledger.data)

    def test_borrower_cannot_accept_own_request(self):
        with self.app.app_context():
            tomorrow = (date.today() + timedelta(days=20)).isoformat()
            req_id, _ = create_loan_request(
                community_id=1,
                borrower_id=2,
                amount_cents=5000,
                currency="USD",
                reason="Emergency inventory",
                proposed_due_date=tomorrow
            )
            loan_id, err = accept_loan_request(request_id=req_id, lender_id=2)
            self.assertIsNone(loan_id)
            self.assertIn("cannot fund your own", err.lower())

    # -------------------------------------------------------------
    # 4. DUAL ACKNOWLEDGEMENT WORKFLOW (AWAITING AGREEMENT -> ACTIVE)
    # -------------------------------------------------------------
    def test_peer_loan_acceptance_and_dual_acknowledgement(self):
        with self.app.app_context():
            tomorrow = (date.today() + timedelta(days=30)).isoformat()
            req_id, _ = create_loan_request(
                community_id=1,
                borrower_id=2,
                amount_cents=10000,
                currency="USD",
                reason="Hardware tools",
                proposed_due_date=tomorrow
            )

            # User 1 (lender) accepts User 2's request
            loan_id, err = accept_loan_request(request_id=req_id, lender_id=1)
            self.assertIsNotNone(loan_id)
            self.assertIsNone(err)

            conn = get_db()
            loan = conn.execute("SELECT * FROM loans WHERE id = ?", (loan_id,)).fetchone()
            # Must start in awaiting_agreement
            self.assertEqual(loan['status'], 'awaiting_agreement')
            self.assertEqual(loan['principal_minor'], 10000)
            self.assertEqual(loan['borrower_accepted'], 0)
            self.assertEqual(loan['lender_accepted'], 1)  # Lender accepted upon creation

            # Step 1: Borrower acknowledges
            success, msg = acknowledge_loan_agreement(loan_id=loan_id, user_id=2)
            self.assertTrue(success)

            # Re-fetch loan
            loan_active = conn.execute("SELECT * FROM loans WHERE id = ?", (loan_id,)).fetchone()
            self.assertEqual(loan_active['status'], 'active', "Loan must transition to active once both parties acknowledge")
            self.assertEqual(loan_active['borrower_accepted'], 1)
            self.assertIsNotNone(loan_active['borrower_accepted_at'])

    # -------------------------------------------------------------
    # 5. REPAYMENT PROCESSING & BALANCE FORMULA TESTS
    # -------------------------------------------------------------
    def test_repayment_balance_reduction_and_settlement(self):
        with self.app.app_context():
            tomorrow = (date.today() + timedelta(days=15)).isoformat()
            # Community 2 has User 3 (admin) and User 1 (member)
            req_id, err_req = create_loan_request(
                community_id=2,
                borrower_id=3,
                amount_cents=6000,
                currency="USD",
                reason="School supplies",
                proposed_due_date=tomorrow
            )
            self.assertIsNotNone(req_id, f"Failed to create request: {err_req}")

            loan_id, err_acc = accept_loan_request(request_id=req_id, lender_id=1)
            self.assertIsNotNone(loan_id, f"Failed to accept loan: {err_acc}")

            acknowledge_loan_agreement(loan_id=loan_id, user_id=3) # Activate

            # Check initial balance: 6000 + 0 = 6000
            principal, fee, total_due, repaid, out = calculate_outstanding_balance(loan_id)
            self.assertEqual(out, 6000)

            # Partial repayment of $20.00 (2000 cents)
            success, res = record_repayment(
                loan_id=loan_id,
                amount_minor=2000,
                reference="SIM-TEST-PARTIAL1",
                user_id=3,
                payment_date=date.today().isoformat()
            )
            self.assertTrue(success)

            _, _, _, repaid_after, out_after = calculate_outstanding_balance(loan_id)
            self.assertEqual(repaid_after, 2000)
            self.assertEqual(out_after, 4000)

            # Attempt to overpay ($50.00 = 5000 cents, exceeding remaining 4000)
            bad_success, bad_err = record_repayment(
                loan_id=loan_id,
                amount_minor=5000,
                reference="SIM-TEST-OVERPAY",
                user_id=3
            )
            self.assertFalse(bad_success)
            self.assertIn("cannot exceed the outstanding balance", bad_err.lower())

            # Full settlement of remaining $40.00 (4000 cents)
            full_success, full_res = record_repayment(
                loan_id=loan_id,
                amount_minor=4000,
                reference="SIM-TEST-FULL2",
                user_id=3
            )
            self.assertTrue(full_success)
            self.assertTrue(full_res['is_fully_repaid'])

            conn = get_db()
            settled_loan = conn.execute("SELECT * FROM loans WHERE id = ?", (loan_id,)).fetchone()
            self.assertEqual(settled_loan['status'], 'repaid', "Loan must be automatically marked repaid when balance reaches 0")

    # -------------------------------------------------------------
    # 6. OVERDUE DETECTION AND STATUS INDICATORS
    # -------------------------------------------------------------
    def test_overdue_sync_functionality(self):
        with self.app.app_context():
            future_due = (date.today() + timedelta(days=10)).isoformat()
            req_id, _ = create_loan_request(
                community_id=1,
                borrower_id=4,
                amount_cents=3000,
                currency="USD",
                reason="Medical emergency",
                proposed_due_date=future_due
            )
            loan_id, _ = accept_loan_request(request_id=req_id, lender_id=1)
            acknowledge_loan_agreement(loan_id=loan_id, user_id=4)

            # Fast-forward / force loan due date to 5 days in the past
            yesterday = (date.today() - timedelta(days=5)).isoformat()
            conn = get_db()
            conn.execute("UPDATE loans SET due_date = ? WHERE id = ?", (yesterday, loan_id))
            conn.commit()

            # Run sync
            synced_count = sync_overdue_loans()
            self.assertGreaterEqual(synced_count, 1)

            loan = conn.execute("SELECT * FROM loans WHERE id = ?", (loan_id,)).fetchone()
            self.assertEqual(loan['status'], 'overdue')

    # -------------------------------------------------------------
    # 7. CSV EXPORT & HTTP ENDPOINTS TESTS
    # -------------------------------------------------------------
    def test_analytics_and_csv_exports(self):
        # Switch persona to admin (User 7)
        resp_switch = self.client.get('/switch-user/7', follow_redirects=True)
        self.assertEqual(resp_switch.status_code, 200)

        # Check /dashboard
        resp_dash = self.client.get('/dashboard')
        self.assertEqual(resp_dash.status_code, 200)
        self.assertIn(b"Lending Portfolio Overview", resp_dash.data)

        # Check /analytics
        resp_analytics = self.client.get('/analytics')
        self.assertEqual(resp_analytics.status_code, 200)
        self.assertIn(b"Fintech Performance Analytics", resp_analytics.data)

        # Test CSV Export for Loans
        resp_csv = self.client.get('/analytics/export/loans')
        self.assertEqual(resp_csv.status_code, 200)
        self.assertEqual(resp_csv.mimetype, 'text/csv')
        self.assertIn(b"id,request_id,lender_id,borrower_id", resp_csv.data)

        # Test CSV Export for Repayments
        resp_rep_csv = self.client.get('/analytics/export/repayments')
        self.assertEqual(resp_rep_csv.status_code, 200)
        self.assertEqual(resp_rep_csv.mimetype, 'text/csv')
        self.assertIn(b"id,loan_id,amount_minor", resp_rep_csv.data)

if __name__ == '__main__':
    unittest.main()
