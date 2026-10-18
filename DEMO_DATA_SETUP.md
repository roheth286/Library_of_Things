# DEMO DATA SETUP & PREPARATION GUIDE
## Library of Things — Database Systems Project

This document details the exact demonstration dataset, account provisioning procedures, schema initialization, and repeatable reset steps for demonstrating the **Library of Things** project.

---

### 1. Prerequisites and Database Initialization

Ensure PostgreSQL 15 or 16 is running locally.

To initialize the database from scratch:
```powershell
# In PowerShell (Windows)
# Create database
psql -U postgres -c "DROP DATABASE IF EXISTS circulend WITH (FORCE);"
psql -U postgres -c "CREATE DATABASE circulend;"

# If the circulend database user does not exist:
psql -U postgres -c "DO \$\$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='circulend') THEN CREATE ROLE circulend WITH LOGIN PASSWORD 'circulend' SUPERUSER; END IF; END \$\$;"

# Run schema and logic scripts in strict order:
$env:PGPASSWORD="circulend"
psql -h localhost -U circulend -d circulend -f db/01_schema.sql
psql -h localhost -U circulend -d circulend -f db/02_logic.sql
psql -h localhost -U circulend -d circulend -f db/03_security.sql
psql -h localhost -U circulend -d circulend -f db/04_lab.sql
```

---

### 2. Seeding Demonstration Data

Run the deterministic seed script:
```powershell
python db/seed.py
```

This creates a clean, deterministic demonstration environment:
- **50 Member Accounts** (names, contacts, bcrypt password hashes).
- **8 Categories**: Power Tools, Hand Tools, Garden & Outdoor, Kitchen, Camping, Cleaning, Electronics & Measuring, Party & Events.
- **33 Tool Types**: Drills, Saws, Mowers, Tents, Pressure Washers, Mixers, Multimeters, etc.
- **80 Physical Units**: Assigned serial numbers (e.g. `CL-001-01`), status indicators (`Available`, `Loaned`, `Reserved`, `Repair`), and condition statuses (`Good`, `Fair`, `Needs Inspection`, `Repair`).
- **6 Multi-Item Equipment Kits**: Each mapped to 3–4 required tool types in `kit_components`.
- **~190 Historical Loans & Deposits**: Non-overlapping historical usage and deposit holds for dashboard analytics.

---

### 3. Key Demonstration Accounts

All pre-seeded demo accounts use the standard demo password: **`circulend123`**.

| Role | Name | Email | Password | Purpose in Demonstration |
|---|---|---|---|---|
| **Admin** | Admin User | `admin@circulend.in` | `circulend123` | Full access to Staff Desk, Dashboard, Concurrency Lab, and Reset Demo API |
| **Staff** | Staff Meena | `staff.meena@circulend.in` | `circulend123` | Demonstrates Check-out, Returns, Damage Reports, Repair Bench, Deposits, Expiry Jobs |
| **Staff** | Staff Ravi | `staff.ravi@circulend.in` | `circulend123` | Secondary staff operator |
| **Member** | Seeded Member (e.g. Aarav Kumar) | `aarav.kumar@example.in` | `circulend123` | Pre-existing member with active loans, reservations, and notifications |
| **New User** | Demonstration Member | *Created during video registration* | *Compliant password* | Demonstrates live public registration & password policy rules |

---

### 4. Key Equipment Prepared for Live Demonstrations

| Tool Name | Key Unit / Detail | Status / Setup | What it Demonstrates in the Video |
|---|---|---|---|
| **Jigsaw** | Category: Power Tools | Has Available units (`CL-005-01`) | Member makes an immediate successful reservation (`sp_reserve`). |
| **Pressure Washer** | Category: Garden & Outdoor | All units currently `Loaned` / 0 available | Member attempts to reserve → automatically placed on **Waitlist** with queue position. |
| **Pressure Washer** | Unit in Open Loans table | Loaned out | Staff returns the unit → database cascade immediately promotes the waiting member and creates an active reservation! |
| **Cordless Drill** | Unit in Open Loans table | Loaned out | Staff return with **Major** damage → `trg_damage_flag` auto-sets condition to `Repair` and removes it from circulation. |
| **Cordless Drill** | In `Repair bench` | Status: `Repair` | Staff clicks "Repair done" (`sp_complete_repair`) → unit returns to `Available` in circulation. |
| **Home Renovation Kit** | Requires Tile Cutter, Drill, etc. | Tile cutter is out of stock | Staff clicks "Check out kit" → atomic rollback aborts loan creation because not all components are free. |
| **Weekend Camping Kit** | Tent, Sleeping Bag, Stove, Backpack | All components free | Staff checks out kit → atomic multi-loan creation in a single transaction. |
| **Deposit Holds** | Loan with deposit (e.g. ₹3,500) | Return window open (<24 hrs) | Staff attempts early deposit release → stored procedure rejects: `return window open`. |

---

### 5. Safe Demonstration Dataset Reset Procedure

To reset the database back to its clean starting state at any time before or after recording:

#### Option A: One-Click UI Reset (Administrator Only)
While logged in as an Administrator (`admin@circulend.in`):
1. Open the browser developer console (F12) or call the admin endpoint:
   ```javascript
   await api('/admin/reset-demo', { body: {} });
   ```
2. Or refresh the page and verify that seed data is restored.

#### Option B: Terminal Command (Recommended)
Run the seed script directly from the project root:
```powershell
python db/seed.py
```
*Note: This deterministic script resets history, re-creates demo members, sets up units, and takes less than 2 seconds.*
