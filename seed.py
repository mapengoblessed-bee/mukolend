from datetime import datetime, date, timedelta
from werkzeug.security import generate_password_hash
from database import get_standalone_connection, init_db

def seed_database(db_path=None):
    init_db(db_path)
    conn = get_standalone_connection(db_path)
    cursor = conn.cursor()

    print("Cleaning existing records for fresh seed...")
    cursor.execute("DELETE FROM audit_log")
    cursor.execute("DELETE FROM repayments")
    cursor.execute("DELETE FROM loans")
    cursor.execute("DELETE FROM loan_requests")
    cursor.execute("DELETE FROM community_members")
    cursor.execute("DELETE FROM communities")
    cursor.execute("DELETE FROM users")
    conn.commit()

    print("Seeding Users...")
    pwd_user = generate_password_hash("password123")
    pwd_admin = generate_password_hash("admin12345")

    users_data = [
        (1, "Farai Moyo", "farai@mukolend.co.zw", pwd_user, "user", "2026-09-01 08:30:00"),
        (2, "Tinashe Mutasa", "tinashe@mukolend.co.zw", pwd_user, "user", "2026-09-05 10:15:00"),
        (3, "Chipo Ndlovu", "chipo@mukolend.co.zw", pwd_user, "user", "2026-09-08 14:00:00"),
        (4, "Ruvimbo Chiweshe", "ruvimbo@mukolend.co.zw", pwd_user, "user", "2026-09-12 11:20:00"),
        (5, "Blessing Sibanda", "blessing@mukolend.co.zw", pwd_user, "user", "2026-09-15 09:45:00"),
        (6, "Tariro Sithole", "tariro@mukolend.co.zw", pwd_user, "user", "2026-09-20 16:30:00"),
        (7, "Executive Administrator", "admin@mukolend.co.zw", pwd_admin, "admin", "2026-08-15 08:00:00")
    ]

    cursor.executemany("""
        INSERT INTO users (id, full_name, email, password_hash, role, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, users_data)
    conn.commit()

    print("Seeding Communities...")
    communities_data = [
        (1, "Harare Central Small Traders Mukando", 
         "A trusted micro-credit circle of marketplace vendors in Mbare Magaba, Copacabana, and Gulf Complex providing emergency stock capital.", 
         "MUKO-TRADER", 1, "2026-09-02 09:00:00"),
        
        (2, "Kambuzuma Women & Friends Club", 
         "A neighborhood community savings and peer credit club supporting family health, school fees, and home-based trade.", 
         "MUKO-KAMBUZ", 3, "2026-09-09 10:00:00"),

        (3, "Avondale Professionals Savings Circle", 
         "A peer credit collective of healthcare workers, consultants, and IT freelancers funding bridge projects and equipment.", 
         "MUKO-AVONDL", 4, "2026-09-13 11:00:00"),

        (4, "Chitungwiza Agro-Supply Association", 
         "Horticulture and broiler farmers pooling emergency funds for chick feed, fertilizer, and irrigation maintenance.", 
         "MUKO-CHITNG", 5, "2026-09-16 12:00:00")
    ]

    cursor.executemany("""
        INSERT INTO communities (id, name, description, invite_code, created_by, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, communities_data)
    conn.commit()

    print("Enrolling Members into Communities...")
    memberships = [
        # Community 1
        (1, 1, 'admin', "2026-09-02 09:00:00"),
        (1, 2, 'member', "2026-09-05 11:00:00"),
        (1, 4, 'member', "2026-09-14 09:30:00"),
        (1, 6, 'member', "2026-09-21 10:00:00"),
        
        # Community 2
        (2, 3, 'admin', "2026-09-09 10:00:00"),
        (2, 1, 'member', "2026-09-10 12:00:00"),
        (2, 5, 'member', "2026-09-17 14:00:00"),

        # Community 3
        (3, 4, 'admin', "2026-09-13 11:00:00"),
        (3, 1, 'member', "2026-09-14 15:00:00"),
        (3, 2, 'member', "2026-09-15 16:00:00"),
        (3, 6, 'member', "2026-09-22 09:00:00"),

        # Community 4
        (4, 5, 'admin', "2026-09-16 12:00:00"),
        (4, 2, 'member', "2026-09-18 10:00:00"),
        (4, 3, 'member', "2026-09-19 11:30:00"),
    ]

    cursor.executemany("""
        INSERT INTO community_members (community_id, user_id, role, joined_at)
        VALUES (?, ?, ?, ?)
    """, memberships)
    conn.commit()

    print("Seeding Loan Requests...")
    today = date.today()
    due_future_20 = (today + timedelta(days=20)).strftime("%Y-%m-%d")
    due_future_30 = (today + timedelta(days=30)).strftime("%Y-%m-%d")
    due_future_45 = (today + timedelta(days=45)).strftime("%Y-%m-%d")
    due_past_15 = (today - timedelta(days=15)).strftime("%Y-%m-%d")
    due_past_5 = (today - timedelta(days=5)).strftime("%Y-%m-%d")
    due_soon_2 = (today + timedelta(days=2)).strftime("%Y-%m-%d")

    # 1: Chipo repaid loan request
    # 2: Blessing active loan request
    # 3: Tinashe active loan request (due soon)
    # 4: Tariro accepted loan request (awaiting agreement)
    # 5: Tinashe pending open request
    # 6: Blessing pending open request
    # 7: Overdue loan request
    requests_data = [
        (1, 2, 3, 15000, "USD", "School uniform textile roll consignment purchase for Kambuzuma High orders", due_past_15, "accepted", "2026-09-10 11:00:00"),
        (2, 4, 5, 20000, "USD", "Emergency broiler starter mash and vaccines for 1,000 day-old chicks batch", due_future_20, "accepted", "2026-09-25 09:00:00"),
        (3, 1, 2, 10000, "USD", "Fast-moving tempered glass screens and phone accessories consignment clearance", due_soon_2, "accepted", "2026-10-02 14:00:00"),
        (4, 3, 6, 18000, "USD", "High-speed external NVMe SSD and studio monitor headphones for commercial design client", due_future_30, "accepted", "2026-10-10 16:00:00"),
        (5, 1, 2, 25000, "USD", "Wholesale stock trip for charging cables, smart watches, and Bluetooth earbuds", due_future_30, "pending", "2026-10-15 08:30:00"),
        (6, 4, 5, 35000, "USD", "Drip irrigation pipe repair and solar water pump inverter replacement", due_future_45, "pending", "2026-10-16 12:00:00"),
        (7, 1, 6, 12000, "USD", "Printing flyers and packaging boxes for seasonal market trade", due_past_5, "accepted", "2026-09-15 10:00:00"),
    ]

    cursor.executemany("""
        INSERT INTO loan_requests (id, community_id, borrower_id, amount_minor, currency, reason, proposed_due_date, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, requests_data)
    conn.commit()

    print("Seeding Loans (Agreements)...")
    loans_data = [
        # Loan 1: Fully Repaid
        (1, 1, 1, 3, 15000, 0, "USD", due_past_15, 1, 1, "2026-09-11 10:00:00", "2026-09-11 10:30:00", "repaid", "2026-09-11 10:30:00"),
        
        # Loan 2: Active (Partially Repaid)
        (2, 2, 1, 5, 20000, 0, "USD", due_future_20, 1, 1, "2026-09-26 11:00:00", "2026-09-26 11:15:00", "active", "2026-09-26 11:15:00"),

        # Loan 3: Active (Due Soon in 2 days)
        (3, 3, 4, 2, 10000, 0, "USD", due_soon_2, 1, 1, "2026-10-03 15:00:00", "2026-10-03 15:20:00", "active", "2026-10-03 15:20:00"),

        # Loan 4: Awaiting Agreement (Lender accepted, borrower yet to acknowledge)
        (4, 4, 1, 6, 18000, 0, "USD", due_future_30, 0, 1, None, "2026-10-11 09:00:00", "awaiting_agreement", "2026-10-11 09:00:00"),

        # Loan 5: Overdue Loan
        (5, 7, 1, 6, 12000, 0, "USD", due_past_5, 1, 1, "2026-09-16 11:00:00", "2026-09-16 11:30:00", "overdue", "2026-09-16 11:30:00"),
    ]

    cursor.executemany("""
        INSERT INTO loans (
            id, request_id, lender_id, borrower_id, principal_minor, fee_minor, currency,
            due_date, borrower_accepted, lender_accepted, borrower_accepted_at,
            lender_accepted_at, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, loans_data)
    conn.commit()

    print("Seeding Simulated Repayments...")
    repayments_data = [
        # Full repayment for Loan 1 ($150.00 = 15000 cents)
        (1, 1, 15000, "SIM-MUKO-20260920-8812", 3, "2026-09-20", "2026-09-20 14:00:00"),
        
        # Partial repayment for Loan 2 ($100.00 = 10000 cents of 20000 cents)
        (2, 2, 10000, "SIM-MUKO-20261005-4491", 5, "2026-10-05", "2026-10-05 16:30:00"),

        # Partial repayment for Overdue Loan 5 ($40.00 = 4000 cents of 12000 cents)
        (3, 5, 4000, "SIM-MUKO-20260928-1029", 6, "2026-09-28", "2026-09-28 11:15:00")
    ]

    cursor.executemany("""
        INSERT INTO repayments (id, loan_id, amount_minor, reference, recorded_by, payment_date, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, repayments_data)
    conn.commit()

    print("Seeding Audit Log Records...")
    audit_data = [
        (1, 1, "USER_REGISTERED", "user", 1, "2026-09-01 08:30:00"),
        (2, 1, "COMMUNITY_CREATED", "community", 1, "2026-09-02 09:00:00"),
        (3, 2, "COMMUNITY_JOINED", "community", 1, "2026-09-05 11:00:00"),
        (4, 3, "REQUEST_CREATED", "loan_request", 1, "2026-09-10 11:00:00"),
        (5, 1, "REQUEST_ACCEPTED", "loan_request", 1, "2026-09-11 10:30:00"),
        (6, 3, "AGREEMENT_ACKNOWLEDGED", "loan", 1, "2026-09-11 10:00:00"),
        (7, 1, "LOAN_ACTIVATED", "loan", 1, "2026-09-11 10:30:00"),
        (8, 3, "REPAYMENT_SETTLED_FULL", "repayment", 1, "2026-09-20 14:00:00"),
        (9, 5, "REPAYMENT_RECORDED_PARTIAL", "repayment", 2, "2026-10-05 16:30:00"),
        (10, None, "LOAN_MARKED_OVERDUE", "loan", 5, "2026-10-14 00:01:00"),
    ]

    cursor.executemany("""
        INSERT INTO audit_log (id, actor_id, action, entity_type, entity_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, audit_data)
    conn.commit()

    conn.close()
    print("Database seeding completed successfully with realistic Zimbabwean Mukando scenarios!")

if __name__ == '__main__':
    seed_database()
