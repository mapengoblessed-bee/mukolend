import unittest
from app import app
from database import get_db, init_db
from seed_data import seed_database

class MukoLendTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        seed_database()

    def setUp(self):
        self.client = app.test_client()

    def test_homepage(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Borrow Through", response.data)
        self.assertIn(b"Repay With", response.data)
        self.assertIn(b"Mukando", response.data)

    def test_marketplace(self):
        response = self.client.get('/marketplace')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Open Mukando Loan Requests", response.data)

    def test_groups_directory(self):
        response = self.client.get('/groups')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Harare Central Small Traders", response.data)

    def test_group_detail(self):
        response = self.client.get('/groups/1')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Harare Central Small Traders Mukando", response.data)
        self.assertIn(b"Group Loan Ledger", response.data)

    def test_loan_detail(self):
        response = self.client.get('/loans/1')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"MKL-2026-0812", response.data)
        self.assertIn(b"Fulfilled & Fully Settled", response.data)

    def test_promissory_contract(self):
        response = self.client.get('/loans/1/contract')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"COMMUNITY PROMISSORY NOTE", response.data)
        self.assertIn(b"Chipo Ndlovu", response.data)
        self.assertIn(b"Farai Moyo", response.data)

    def test_user_switcher_and_dashboard(self):
        # Switch to Farai (Lender, ID 1)
        self.client.get('/switch_user/1')
        resp = self.client.get('/dashboard')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(b"Farai Moyo" in resp.data, "Farai Moyo not in dashboard")
        self.assertTrue(b"Hardware &amp; Agro Merchant" in resp.data or b"Hardware" in resp.data, "Farai occupation not in dashboard")

        # Switch to Tinashe (Borrower, ID 2)
        self.client.get('/switch_user/2')
        resp = self.client.get('/dashboard')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(b"Tinashe Mutasa" in resp.data, "Tinashe Mutasa not in dashboard")

    def test_lending_and_repayment_flow(self):
        # 1. Switch to Farai (Lender, ID 1)
        self.client.get('/switch_user/1')

        # 2. Fund Loan 4 (Tinashe's $250 request)
        resp = self.client.post('/loans/4/fund', follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Funded", resp.data)

        # 3. Disburse funds
        resp = self.client.post('/loans/4/disburse', data={
            'payment_method': 'EcoCash',
            'disbursement_reference': 'EC-TEST-9999',
            'notes': 'Sent to Tinashe via EcoCash USD'
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Active & In Repayment", resp.data)

        # 4. Switch to Tinashe (Borrower, ID 2)
        self.client.get('/switch_user/2')

        # 5. Make a partial repayment of $100
        resp = self.client.post('/loans/4/repay', data={
            'amount': '100.00',
            'payment_method': 'EcoCash',
            'transaction_reference': 'EC-REPAY-1',
            'notes': 'First partial installment'
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Partial repayment of $100.00", resp.data)

        # 6. Make final repayment of remaining $175 (Total was $275)
        resp = self.client.post('/loans/4/repay', data={
            'amount': '175.00',
            'payment_method': 'EcoCash',
            'transaction_reference': 'EC-REPAY-2',
            'notes': 'Final settlement'
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Fulfilled & Fully Settled", resp.data)

        # 7. Leave a mutual trust review
        resp = self.client.post('/loans/4/review', data={
            'rating': '5',
            'comment': 'Mukoma Farai was prompt and supportive. Seamless Mukando lending!'
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"review has been published", resp.data)

    def test_api_calculator(self):
        resp = self.client.post('/api/calculate', json={
            'principal': 200,
            'rate': 10,
            'days': 30
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data['interest'], 20.0)
        self.assertEqual(data['total'], 220.0)

if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(MukoLendTestCase)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    for failure in result.failures:
        print("FAILED TEST:", failure[0].id())
        print("REASON:", failure[1].splitlines()[-1])
    for error in result.errors:
        print("ERROR TEST:", error[0].id())
        print("REASON:", error[1].splitlines()[-1])
    if result.wasSuccessful():
        print("ALL TESTS PASSED SUCCESSFULLY!")
