from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta, date
from database import get_db, init_db, generate_contract_hash

def dt_str(days_ago=0, hours_ago=0):
    dt = datetime.now() - timedelta(days=days_ago, hours=hours_ago)
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def date_str(days_from_now=0):
    d = date.today() + timedelta(days=days_from_now)
    return d.strftime("%Y-%m-%d")

def seed_database():
    init_db()
    conn = get_db()
    cursor = conn.cursor()

    # Clear existing data
    cursor.execute("DELETE FROM notifications")
    cursor.execute("DELETE FROM reviews")
    cursor.execute("DELETE FROM loan_timeline")
    cursor.execute("DELETE FROM repayments")
    cursor.execute("DELETE FROM loan_vouches")
    cursor.execute("DELETE FROM loans")
    cursor.execute("DELETE FROM group_members")
    cursor.execute("DELETE FROM groups")
    cursor.execute("DELETE FROM users")
    conn.commit()

    print("Populating MukoLend users...")
    password_hash = generate_password_hash("password123")

    users_data = [
        (1, "Farai Moyo", "farai@mukolend.co.zw", password_hash, "+263 77 234 5678", "Mbare Magaba, Harare", "Hardware & Agro Merchant", "Active community lender and treasurer. Committed to supporting fellow business owners through transparent Mukando lending.", 94, "#059669", 1),
        (2, "Tinashe Mutasa", "tinashe@mukolend.co.zw", password_hash, "+263 71 890 1234", "Copacabana, Harare", "Electronics & Phone Accessories Vendor", "Running a tech stall for 4 years. Frequent borrower who always prioritizes timely settlement through EcoCash.", 82, "#2563EB", 1),
        (3, "Chipo Ndlovu", "chipo@mukolend.co.zw", password_hash, "+263 77 912 3456", "Kambuzuma Section 3, Harare", "School Uniforms & Textile Designer", "Founder of Kambuzuma Savings Club. Believes trust and open communication are the backbone of community wealth.", 98, "#7C3AED", 1),
        (4, "Ruvimbo Chiweshe", "ruvimbo@mukolend.co.zw", password_hash, "+263 78 456 7890", "Avondale, Harare", "Nurse & Medical Supplies Agent", "Lender and peer voucher. Looking to grow our community savings while helping members bridge cashflow gaps.", 88, "#EA580C", 1),
        (5, "Blessing Sibanda", "blessing@mukolend.co.zw", password_hash, "+263 73 345 6789", "Unit L, Chitungwiza", "Poultry & Horticulture Farmer", "Operating 1,000 broiler batch. Uses short-term Mukando loans for chick feed during market transition periods.", 78, "#0D9488", 1),
        (6, "Tariro Sithole", "tariro@mukolend.co.zw", password_hash, "+263 77 111 2233", "Eastlea, Harare", "Graphic Designer & Freelancer", "Creative professional using MukoLend to upgrade studio equipment through peer trust agreements.", 85, "#DB2777", 1),
    ]

    cursor.executemany("""
        INSERT INTO users (id, name, email, password_hash, phone, location, occupation, bio, trust_score, avatar_color, is_verified)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, users_data)
    conn.commit()

    print("Populating Mukando Groups...")
    groups_data = [
        (1, "Harare Central Small Traders Mukando", 
         "A high-frequency savings and lending circle of trusted vendors across Mbare Magaba, Copacabana, and Gulf Complex. Focuses on quick 14-30 day stock loans with transparent community auditing.",
         "Market Traders", "Harare CBD & Mbare", 1, 
         "Maximum loan $400. Term 14-30 days. Standard community interest 10%. At least 1 member vouch required before funding.", 
         1850.0, "Weekly $20 Pool"),
        
        (2, "Kambuzuma Women & Friends Savings Club",
         "Established in 2021 by neighborhood entrepreneurs and families. We pool emergency funds and offer micro-loans for school fees, family events, and tuckshop inventory.",
         "Family & Neighborhood", "Kambuzuma, Harare", 3,
         "Loans from $30 up to $250. Flexible terms up to 45 days. Mutual review required after settlement. Zero tolerance for uncommunicated delays.",
         1200.0, "Monthly $30 Pool"),

        (3, "Avondale Professionals Savings Circle",
         "A digital-first savings association for freelancers, consultants, and health professionals seeking bridge funding for equipment, certification, and project buffers.",
         "Professional ASCA", "Avondale & Eastlea", 4,
         "Loans up to $600. Term 30-60 days. 8% interest rate. Disbursement via InnBucks or EcoCash USD.",
         3400.0, "Monthly $50 Pool"),

        (4, "Chitungwiza Agro-Supply Circle",
         "Peri-urban farmers and suppliers collaborating to fund seasonal livestock feed, fertilizer, and irrigation maintenance.",
         "Agricultural", "Chitungwiza", 5,
         "Seasonal terms up to 60 days. 12% interest. Field verification by club inspectors for first-time loans above $200.",
         950.0, "Bi-weekly $25 Pool")
    ]

    cursor.executemany("""
        INSERT INTO groups (id, name, description, category, location, created_by, rules, group_pool_balance, contribution_cycle)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, groups_data)
    conn.commit()

    print("Enrolling Members into Groups...")
    members_data = [
        # Group 1: Harare Central Small Traders
        (1, 1, 'admin', 350.0),
        (1, 2, 'member', 200.0),
        (1, 4, 'member', 250.0),
        (1, 6, 'member', 150.0),
        
        # Group 2: Kambuzuma Women & Friends
        (2, 3, 'admin', 450.0),
        (2, 1, 'member', 150.0),
        (2, 5, 'member', 210.0),

        # Group 3: Avondale Professionals
        (3, 4, 'admin', 500.0),
        (3, 1, 'member', 300.0),
        (3, 2, 'member', 250.0),
        (3, 6, 'member', 400.0),

        # Group 4: Chitungwiza Agro-Supply
        (4, 5, 'admin', 320.0),
        (4, 2, 'member', 180.0),
        (4, 3, 'member', 220.0),
    ]

    cursor.executemany("""
        INSERT INTO group_members (group_id, user_id, role, total_contributed)
        VALUES (?, ?, ?, ?)
    """, members_data)
    conn.commit()

    print("Seeding Loans & Realistic Scenarios...")
    
    # 1. Loan 1: Fully Repaid Historical Loan (Chipo borrowed from Farai)
    contract_hash_1 = generate_contract_hash(1, 3, 1, 150.0, date_str(-20))
    cursor.execute("""
        INSERT INTO loans (
            id, loan_reference, group_id, borrower_id, lender_id, principal_amount, 
            interest_rate_percent, interest_amount, total_payable, purpose, purpose_category, 
            duration_days, disbursement_method, status, requested_at, funded_at, disbursed_at, 
            due_date, fully_repaid_at, disbursement_reference, disbursement_notes, contract_hash
        ) VALUES (
            1, 'MKL-2026-0812', 2, 3, 1, 150.0, 
            10.0, 15.0, 165.0, 'Purchased 4 rolls of school blazer fabric for term 1 orders', 'Business & Working Capital',
            30, 'EcoCash', 'repaid', 
            ?, ?, ?,
            ?, ?, 'EC-98231019A', 'Sent to Chipo 0779123456 with EcoCash USD', ?
        )
    """, (dt_str(45), dt_str(44), dt_str(44), date_str(-14), dt_str(18), contract_hash_1))

    # Repayment for Loan 1
    cursor.execute("""
        INSERT INTO repayments (loan_id, payer_id, amount, payment_method, transaction_reference, notes, paid_at)
        VALUES (1, 3, 165.0, 'EcoCash', 'EC-99482103B', 'Settled in full ahead of time. Thank you Mukoma Farai!', ?)
    """, (dt_str(18),))

    # Timeline for Loan 1
    cursor.executemany("""
        INSERT INTO loan_timeline (loan_id, actor_id, event_type, title, description, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, [
        (1, 3, 'REQUESTED', 'Loan Request Created', 'Chipo requested $150 for school blazer material.', dt_str(45)),
        (1, 1, 'FUNDED', 'Offer Accepted by Lender', 'Farai agreed to fund $150 with 10% markup.', dt_str(44)),
        (1, 1, 'DISBURSED', 'Disbursement Completed', 'Funds disbursed via EcoCash ref EC-98231019A.', dt_str(44)),
        (1, 3, 'REPAYMENT_FULL', 'Full Repayment Recorded', 'Chipo paid $165.00 via EcoCash ref EC-99482103B.', dt_str(18)),
        (1, 1, 'SETTLED', 'Loan Closed & Trust Updated', 'Agreement completed with honors. Trust score boosted.', dt_str(18)),
    ])

    # Reviews for Loan 1
    cursor.execute("""
        INSERT INTO reviews (loan_id, reviewer_id, reviewee_id, role, rating, comment, created_at)
        VALUES (1, 1, 3, 'lender_reviewing_borrower', 5, 'Chipo settled 4 days before due date without even needing a reminder. Top tier Mukando partner!', ?)
    """, (dt_str(17),))
    cursor.execute("""
        INSERT INTO reviews (loan_id, reviewer_id, reviewee_id, role, rating, comment, created_at)
        VALUES (1, 3, 1, 'borrower_reviewing_lender', 5, 'Mukoma Farai sent the EcoCash within 15 minutes of signing the agreement. Highly transparent and supportive.', ?)
    """, (dt_str(17),))

    # 2. Loan 2: Active Loan (Blessing borrowed from Farai, partially repaid)
    contract_hash_2 = generate_contract_hash(2, 5, 1, 200.0, date_str(12))
    cursor.execute("""
        INSERT INTO loans (
            id, loan_reference, group_id, borrower_id, lender_id, principal_amount, 
            interest_rate_percent, interest_amount, total_payable, purpose, purpose_category, 
            duration_days, disbursement_method, status, requested_at, funded_at, disbursed_at, 
            due_date, fully_repaid_at, disbursement_reference, disbursement_notes, contract_hash
        ) VALUES (
            2, 'MKL-2026-1049', 4, 5, 1, 200.0, 
            12.0, 24.0, 224.0, 'Emergency broiler starter mash & vaccines for new chick batch', 'Agriculture & Livestock',
            30, 'InnBucks', 'active', 
            ?, ?, ?,
            ?, NULL, 'IB-4981023', 'Transferred via InnBucks agent code at Makoni Shopping Centre', ?
        )
    """, (dt_str(18), dt_str(18), dt_str(17), date_str(12), contract_hash_2))

    # Partial Repayment for Loan 2 ($100 of $224 paid)
    cursor.execute("""
        INSERT INTO repayments (loan_id, payer_id, amount, payment_method, transaction_reference, notes, paid_at)
        VALUES (2, 5, 100.0, 'InnBucks', 'IB-5520194', 'First installment from sale of early dressed broilers', ?)
    """, (dt_str(3),))

    # Timeline for Loan 2
    cursor.executemany("""
        INSERT INTO loan_timeline (loan_id, actor_id, event_type, title, description, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, [
        (2, 5, 'REQUESTED', 'Loan Request Created', 'Blessing requested $200 for chick mash and vaccines.', dt_str(18)),
        (2, 1, 'FUNDED', 'Accepted by Farai', 'Farai funded the request under Chitungwiza Agro-Supply terms.', dt_str(18)),
        (2, 1, 'DISBURSED', 'Disbursed via InnBucks', 'Transferred via InnBucks ref IB-4981023.', dt_str(17)),
        (2, 5, 'REPAYMENT_PARTIAL', 'Partial Payment Received', 'Blessing paid $100.00 via InnBucks. Remaining balance: $124.00.', dt_str(3)),
    ])

    # 3. Loan 3: Active Loan (Tinashe borrowed from Ruvimbo)
    contract_hash_3 = generate_contract_hash(3, 2, 4, 100.0, date_str(5))
    cursor.execute("""
        INSERT INTO loans (
            id, loan_reference, group_id, borrower_id, lender_id, principal_amount, 
            interest_rate_percent, interest_amount, total_payable, purpose, purpose_category, 
            duration_days, disbursement_method, status, requested_at, funded_at, disbursed_at, 
            due_date, fully_repaid_at, disbursement_reference, disbursement_notes, contract_hash
        ) VALUES (
            3, 'MKL-2026-1188', 1, 2, 4, 100.0, 
            10.0, 10.0, 110.0, 'Fast-moving phone screens & tempered glass consignment clearance', 'Business & Working Capital',
            14, 'EcoCash', 'active', 
            ?, ?, ?,
            ?, NULL, 'EC-4491028', 'Disbursed via EcoCash USD wallet to Tinashe', ?
        )
    """, (dt_str(9), dt_str(9), dt_str(9), date_str(5), contract_hash_3))

    # Timeline for Loan 3
    cursor.executemany("""
        INSERT INTO loan_timeline (loan_id, actor_id, event_type, title, description, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, [
        (3, 2, 'REQUESTED', 'Loan Request Created', 'Tinashe requested $100 for phone accessories consignment clearance.', dt_str(9)),
        (3, 4, 'FUNDED', 'Accepted by Ruvimbo', 'Ruvimbo agreed to fund 14-day stock loan.', dt_str(9)),
        (3, 4, 'DISBURSED', 'Funds Sent via EcoCash', 'EcoCash USD transaction EC-4491028 confirmed.', dt_str(9)),
    ])

    # 4. Loan 4: Open Request on Marketplace (Tinashe requesting $250 for Musina shopping trip)
    cursor.execute("""
        INSERT INTO loans (
            id, loan_reference, group_id, borrower_id, lender_id, principal_amount, 
            interest_rate_percent, interest_amount, total_payable, purpose, purpose_category, 
            duration_days, disbursement_method, status, requested_at, due_date
        ) VALUES (
            4, 'MKL-2026-1250', 1, 2, NULL, 250.0, 
            10.0, 25.0, 275.0, 'Musina wholesale trip for memory cards, charging cables, and smart watches', 'Business & Working Capital',
            21, 'EcoCash', 'requested', 
            ?, ?
        )
    """, (dt_str(1), date_str(20)))

    # Vouches for Loan 4 (Chipo vouched for Tinashe!)
    cursor.execute("""
        INSERT INTO loan_vouches (loan_id, voucher_id, relationship, comment, vouched_at)
        VALUES (4, 3, 'Fellow Market Associate', 'I have known Tinashe at Copacabana market for 3 years. He is dependable and never defaults on his word.', ?)
    """, (dt_str(0, 18),))

    cursor.executemany("""
        INSERT INTO loan_timeline (loan_id, actor_id, event_type, title, description, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, [
        (4, 2, 'REQUESTED', 'Loan Request Submitted', 'Tinashe created a new loan request for $250 with 10% agreed markup over 21 days.', dt_str(1)),
        (4, 3, 'VOUCHED', 'Community Vouch Added', 'Chipo Ndlovu endorsed this request with a verified voucher badge.', dt_str(0, 18)),
    ])

    # 5. Loan 5: Another Open Request (Tariro requesting $180 for studio equipment)
    cursor.execute("""
        INSERT INTO loans (
            id, loan_reference, group_id, borrower_id, lender_id, principal_amount, 
            interest_rate_percent, interest_amount, total_payable, purpose, purpose_category, 
            duration_days, disbursement_method, status, requested_at, due_date
        ) VALUES (
            5, 'MKL-2026-1304', 3, 6, NULL, 180.0, 
            8.0, 14.4, 194.4, 'Upgrade studio equipment: High-speed NVMe drive & monitor headphones for ongoing commercial client contract', 'Professional Equipment',
            30, 'InnBucks', 'requested', 
            ?, ?
        )
    """, (dt_str(0, 6), date_str(30)))

    cursor.execute("""
        INSERT INTO loan_timeline (loan_id, actor_id, event_type, title, description, created_at)
        VALUES (5, 6, 'REQUESTED', 'Loan Request Submitted', 'Tariro requested $180 for audio and production gear in Avondale Professionals circle.', ?)
    """, (dt_str(0, 6),))

    # Notifications
    cursor.executemany("""
        INSERT INTO notifications (user_id, title, message, link, is_read, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, [
        (1, "New Loan Request in Traders Mukando", "Tinashe Mutasa requested a $250 loan. Chipo Ndlovu has vouched for him.", "/loans/4", 0, dt_str(0, 17)),
        (2, "Repayment Reminder", "Your $110 loan from Ruvimbo is due in 5 days (EcoCash).", "/loans/3", 0, dt_str(0, 5)),
        (5, "Partial Payment Recorded", "Your $100 payment was credited. Remaining balance is $124.00.", "/loans/2", 1, dt_str(3)),
        (3, "Vouch Successful", "Thank you for vouching for Tinashe Mutasa's $250 loan request.", "/loans/4", 1, dt_str(0, 18)),
    ])

    conn.commit()
    conn.close()
    print("MukoLend database successfully initialized and seeded with authentic Zimbabwean Mukando data!")

if __name__ == '__main__':
    seed_database()
