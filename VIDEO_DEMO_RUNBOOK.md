# VIDEO DEMONSTRATION RUNBOOK
## Library of Things — Complete Step-by-Step Recording Guide

This runbook gives you an exact, click-by-click script to record a professional demonstration video of the **Library of Things** project.

Follow this guide sequentially from Section 1 to Section 16.

---

### Section 0: Environment Startup & Setup (Pre-Recording)

#### 0.1 Prerequisites Check
- **Python**: 3.10+ installed (`python --version`).
- **PostgreSQL**: 15 or 16 running locally on port `5432`.
- **Browser**: Chrome, Edge, or Brave.

#### 0.2 Terminal Commands to Launch
Open PowerShell in `c:\Users\rohet\OneDrive\Documents\CS_WORK\college_projects\Library_of_Things`:
```powershell
# 1. Reset database to clean demo state
python db/seed.py

# 2. Start the web application
python app/app.py
```
Expected output:
```text
 * Serving Flask app 'app'
 * Running on http://127.0.0.1:5000 (Press CTRL+C to quit)
```

#### 0.3 Browser Setup
- Open your browser to `http://localhost:5000`.
- Press `F11` (or adjust window to 1920x1080) for a clean presentation.
- Open a second terminal window (or tab) ready to run `python -m pytest tests -q` when demonstrating test suites.

---

### Section 1: Introduction & Project Overview (Estimated Duration: 1m 00s)

#### On Screen:
Open `http://localhost:5000` showing the **Landing Page**.

#### What to Say & Point Out:
- *"Welcome to the demonstration of **Library of Things**, a database-driven community tool and equipment sharing platform developed for the Database Systems Lab (BCSE302P)."*
- *"Rather than each household purchasing expensive, rarely used tools like pressure washers, lawnmowers, and tile cutters, Library of Things facilitates borrowing and community sharing."*
- Point out the browser tab title: **"Library of Things - community tool & equipment sharing"**.
- Point out the top navigation bar brand logo: **"Library of Things"** on the left with prominent **Login** and **Register** buttons.

---

### Section 2: Landing Page & Feature Architecture (Estimated Duration: 1m 30s)

#### What to Click & Show:
1. **Hero Section**:
   - Highlight the headline: *"Borrow What You Need. Share What You Have."*
   - Point out the two clear calls-to-action: "Create an Account" and "Sign In".
2. **Platform Features Grid**:
   - Scroll slowly down to the 8 feature cards:
     1. **Equipment Catalogue**: Categorized tools with deposit terms.
     2. **Live Availability**: Real-time physical unit tracking (`Available`, `Loaned`, `Reserved`, `Repair`).
     3. **Reservations**: Mathematical non-overlapping reservation exclusion constraints in PostgreSQL.
     4. **Borrowing & Returns**: Lifecycle management with automated late-fee calculation.
     5. **Waitlists**: FIFO queue cascades when popular equipment returns.
     6. **Condition & Damage Tracking**: Database triggers that automatically flag damaged units for repair.
     7. **Equipment Kits**: Multi-tool bundles that check out atomically.
     8. **Secure Role-Based Access**: Multi-layer security combining JWT, PostgreSQL RLS (`circulend_member`, `circulend_staff`), and stored procedures.
3. **How It Works**:
   - Scroll through the 3 simple steps (Browse Catalogue → Reserve & Collect → Return for Others).
4. **Footer**:
   - Show the clean footer confirming the platform identity and technical stack (PostgreSQL + Flask).

---

### Section 3: Member Registration & Security Validation (Estimated Duration: 2m 00s)

#### What to Click & Demonstrate:
1. Click the **"Register"** button in the top navigation (or the "Create an Account" button in the hero).
2. The registration form opens with fields: Full Name, Email Address, Password, Confirm Password, and Account Role (fixed as "User / Member").

#### Demonstration 3.1: Negative Validation Tests (Show Error Handling)
- **Invalid Email**:
  - Enter Name: `Test User`
  - Enter Email: `invalid-email`
  - Notice the real-time client warning: *"Please enter a valid email address"*.
- **Password Security Policy Demonstration**:
  - Click on the password field and begin typing slowly.
  - Notice the **live dynamic checklist** verifying all 5 security requirements:
    1. *At least 8 characters long*
    2. *At least one numeric digit (0–9)*
    3. *At least one uppercase English letter (A–Z)*
    4. *At least one lowercase English letter (a–z)*
    5. *At least one special character (!, @, #, $, %, etc.)*
  - Type `Weakpw1` → The special character rule remains unmet (red/unmet marker).
  - Type `!` → Notice all 5 checklist indicators turn green with checkmarks (`✓`).
- **Mismatched Password**:
  - In Confirm Password, type `DifferentPassword1!`.
  - Notice the live hint: *"Passwords do not match"*. Click "Register Account" → form refuses submission.

#### Demonstration 3.2: Successful User Registration
- Enter valid registration details:
  - **Full Name**: `Priya Sharma`
  - **Email**: `priya.sharma@example.in`
  - **Password**: `PriyaSecure2026!`
  - **Confirm Password**: `PriyaSecure2026!`
- Click **"Register Account"**.
- **Expected Outcome**:
  - A green notification toast pops up: *"Registration successful. Please sign in."*
  - The view automatically transitions to the **Sign In** screen with Priya's email pre-filled.
  - *Database Note*: The password was hashed using bcrypt (`crypt(..., gen_salt('bf'))`) directly in PostgreSQL—never stored in plaintext.

---

### Section 4: Authentication & Role Enforcement (Estimated Duration: 2m 00s)

#### Demonstration 4.1: Member Login & Role Boundary
1. On the **Sign In** screen:
   - Email: `priya.sharma@example.in`
   - Password: `PriyaSecure2026!`
   - Role Selector: Keep as **"User / Member"**.
2. Click **"Sign in"**.
3. **Expected Outcome**:
   - Green toast: *"Welcome back, Priya Sharma!"*.
   - Header shows user identity: `Priya Sharma (member)` with a "Sign out" button.
   - Member navigation tabs appear: **Browse tools**, **Kits**, **My account**.
   - Privileged tabs (**Staff desk**, **Dashboard**, **Concurrency lab**) are not shown to standard members.

#### Demonstration 4.2: Role Manipulation Prevention (Negative Test)
1. Click **"Sign out"**.
2. Click **"Login"**.
3. Enter Priya's email: `priya.sharma@example.in` and password: `PriyaSecure2026!`.
4. Change the Role dropdown to **"Admin"**.
5. Click **"Sign in"**.
6. **Expected Outcome**:
   - The login attempt is rejected with a red error card: *"Account does not have administrator privileges"*.
   - Explain: *"Selecting 'Admin' in the UI does NOT grant administrator access; the server enforces that the authenticated database record genuinely holds the admin role."*

---

### Section 5: Member Equipment Catalogue & Reservations (Estimated Duration: 2m 30s)

#### What to Click & Demonstrate:
1. Sign back in as a member (e.g. use demo button `Aarav Kumar · member` or type `aarav.kumar@example.in` with password `circulend123`).
2. You land on the **"Browse tools"** page.

#### Demonstration 5.1: Search & Category Filtering
- Type `saw` in the "Search tools..." box → Instant filter shows Circular Saw, Jigsaw, Hand Saw.
- Clear the search box.
- Click category chips: `Power Tools`, `Camping`, `Garden & Outdoor`, `All` → Notice live inventory counts update immediately.
- Point out the visual availability bar on each card:
  - Green = Available
  - Blue = Reserved
  - Amber = Loaned
  - Red = In Repair

#### Demonstration 5.2: Inspecting Physical Units
- On the **"Cordless Drill"** card, click the **"Units"** button.
- A modal dialog appears showing individual physical units:
  - Unit #1, Serial `CL-001-01`, Status, Condition, Due Back date.
  - Unit #2, Unit #3, Unit #4.
- Close the modal.

#### Demonstration 5.3: Successful Immediate Reservation
- Locate **"Jigsaw"** (Category: Power Tools, has Available units).
- Click **"Reserve"**.
- A modal dialog appears:
  - Unit selection: Keep "Next available unit" (or select a specific unit).
  - Start date: Defaults to today.
  - Duration: `3` days.
- Click **"Confirm"**.
- **Expected Outcome**:
  - Green toast: *"Reserved unit #X - reservation #Y"*.
  - Jigsaw's available unit count decrements, and its bar reflects the reservation.

---

### Section 6: Handling Unavailable Equipment & Waitlists (Estimated Duration: 1m 30s)

#### What to Click & Demonstrate:
1. Still on "Browse tools", click the **"Garden & Outdoor"** chip.
2. Locate **"Pressure Washer"** (all units are currently loaned out; badge shows `all out`).
3. Notice the action button automatically reads: **"Join waitlist"**.
4. Click **"Join waitlist"**.
5. Click **"Confirm"** in the reservation dialog.
6. **Expected Outcome**:
   - Green toast: *"All units out - you are #1 on the waitlist"*.
   - The card now displays `1 waiting`.

---

### Section 7: Equipment Kits & Atomic Component Availability (Estimated Duration: 1m 30s)

#### What to Click & Demonstrate:
1. Click the **"Kits"** tab in the top navigation.
2. Explain the business rule:
   - *"A kit is a collection of equipment (e.g., Home Renovation Kit or Weekend Camping Kit). A kit is available only when EVERY single component has a free physical unit."*
3. Show **"Home Renovation Kit"**:
   - Status badge shows: **`Blocked`** (red).
   - Displayed text: *"Blocked by: Tile Cutter"*.
4. Show **"Weekend Camping Kit"**:
   - Status badge shows: **`Available`** (green: 4 of 4 components free).

---

### Section 8: Member Account, History, and Notifications (Estimated Duration: 1m 30s)

#### What to Click & Demonstrate:
1. Click **"My account"** in the top navigation.
2. Walk through the member account panels:
   - **Notifications**: System alerts for reservations, waitlist placements, and deposits.
   - **Waitlist**: Displays current waitlist entries with live queue position (e.g. *Pressure Washer · position #1*).
   - **Active Reservations**: Shows the Jigsaw reservation just made with start date, duration, and a **"Cancel"** button.
   - **Loan History Table**: Full audit history showing past loans, return dates, late fees, and deposits.
3. Click **"Sign out"** to prepare for staff/admin operations.

---

### Section 9: Staff Desk Operations: Handover & Walk-in Checkout (Estimated Duration: 2m 30s)

#### What to Click & Demonstrate:
1. Click **"Login"**.
2. Click the demo account shortcut: **`Staff Meena · staff`** (or enter `staff.meena@circulend.in` / `circulend123`).
3. Select Role: **"Admin"** or leave as default. Click **"Sign in"**.
4. Staff navigation options appear: **Browse tools**, **Kits**, **My account**, **Staff desk**, **Dashboard**, **Concurrency lab**.
5. Click **"Staff desk"**.

#### Demonstration 9.1: Fulfilling an Active Reservation (Handover)
1. Click the **"Reservations to collect"** tab on the Staff desk.
2. Locate the reservation made earlier for Aarav Kumar.
3. Click the **"Hand over"** button.
4. **Expected Outcome**:
   - Stored procedure `sp_checkout` executes with `p_res`.
   - Green toast: *"Handed over - loan #Z"*.
   - The reservation transitions to `Fulfilled` and an active loan is created.

#### Demonstration 9.2: Walk-In Checkout
1. Click the **"Check-out"** tab on the Staff desk.
2. Select member: Choose any member (e.g., *Alice*).
3. Select tool: Choose **"Hand Saw (2 free)"**.
4. Select unit and enter days (`3`).
5. Click **"Check out"**.
6. **Expected Outcome**:
   - Green toast: *"Checked out - loan #W"*.
   - The unit flips from `Available` to `Loaned` in real time.

---

### Section 10: Waitlist Promotion Cascade on Return (Estimated Duration: 2m 00s)

*This is one of the project's most powerful database demonstrations: an automated FIFO trigger cascade.*

#### What to Click & Demonstrate:
1. In the Staff desk, click the **"Open loans"** tab.
2. Locate an active loan for **"Pressure Washer"** (remember Aarav is waiting on the waitlist at position #1!).
3. Click the **"Return…"** button next to Pressure Washer.
4. The Return dialog opens:
   - Condition on return: Select **"No damage"**.
   - Notes: Leave blank.
5. Click **"Complete return"**.
6. **Expected Outcome**:
   - Database trigger `trg_unit_available` executes `fn_waitlist_cascade`.
   - Green toast displays:
     *"Returned. Unit → Reserved. Waitlist: Aarav Kumar promoted to Pressure Washer #1 and notified."*
   - Aarav was automatically granted the reservation, and a notification was generated in the database!

---

### Section 11: Damage Reporting & Automated Quarantine Trigger (Estimated Duration: 2m 00s)

#### What to Click & Demonstrate:
1. Still on **"Open loans"**, find a loan for **"Cordless Drill"**.
2. Click **"Return…"**.
3. In the Return dialog:
   - Condition on return: Select **"Major"**.
   - Notes: Type `Chuck cracked after drop on concrete`.
4. Click **"Complete return"**.
5. **Expected Outcome**:
   - Stored procedure `sp_checkin` inserts a `damage_reports` row.
   - Database trigger `trg_damage_flag` fires automatically.
   - Green toast confirms: *"Returned. Unit → Repair."*
6. Click the **"Repair bench"** tab:
   - The Cordless Drill is listed with Condition: `Repair` and Damage notes: `Major: Chuck cracked after drop on concrete`.
   - Because of the check constraint `chk_repair_not_offered`, it can never accidentally be loaned or reserved while under repair.
7. Click the **"Repair done"** button:
   - Calls `sp_complete_repair`.
   - Green toast: *"Back in circulation - waitlist checked"*.
   - Condition resets to `Good` and status returns to `Available`.

---

### Section 12: Guarded Deposit Release & Business Rules (Estimated Duration: 1m 30s)

#### What to Click & Demonstrate:
1. On the Staff desk, click the **"Deposits"** tab.
2. A table of active deposits appears:
   - Shows Loan #, Member, Tool, Amount (₹), Return Date, and **Releasable? (yes/no)**.
3. Locate a loan where `Releasable?` is **`no`** (the 24-hour hold window is still open).
4. Click the **"Release"** button on that row.
5. **Expected Outcome**:
   - The stored procedure `sp_release_deposit` refuses the transaction!
   - Red toast appears: *"Cannot release: return window open until YYYY-MM-DD HH:MM"*.
   - Explain: *"Deposits are strictly guarded by PostgreSQL logic—staff cannot prematurely release deposits until the mandatory inspection window has passed and no major damage is flagged."*

---

### Section 13: Atomic Kit Checkout (Estimated Duration: 1m 30s)

#### What to Click & Demonstrate:
1. Click the **"Kits"** tab in the top navigation.
2. Show **"Home Renovation Kit"** (Blocked because Tile Cutter is out).
3. Click **"Check out kit…"**.
4. Select a member and click **"Check out all components"**.
5. **Expected Outcome**:
   - Stored procedure `sp_checkout_kit` fails with error code `P0002`.
   - Red toast: *"Kit 'Home Renovation Kit' is unavailable: no free unit of 'Tile Cutter'"*.
   - Due to transaction rollback, **no partial loans** were recorded.
6. Now click **"Weekend Camping Kit"** (where all 4 items are free).
7. Select a member and click **"Check out all components"**.
8. **Expected Outcome**:
   - Green toast: *"Kit checked out: 4 loans"*. All 4 items checked out atomically in a single transaction.

---

### Section 14: Live Analytics Dashboard & Database Views (Estimated Duration: 2m 00s)

#### What to Click & Demonstrate:
1. Click the **"Dashboard"** tab in the top navigation.
2. Explain that every graph and metric is calculated via dedicated SQL views:
   - **Top KPI Cards**: Total Physical Units (80), Members (50), Loans Recorded, Deposits Held (₹).
   - **Live Fleet Status by Category** (`v_fleet_status`): Real-time breakdown of Available, Reserved, Loaned, and Repair units per category.
   - **Average Loan Length by Category** (`v_loan_duration_by_category`): Category duration analytics in days.
   - **Waitlist Length by Tool** (`v_waitlist_by_tool`): Identifies high-demand bottlenecks.
   - **Overdue Loans** (`v_overdue_loans`): Real-time days overdue and accrued late fees (₹20/day).
   - **Most-Used Tools** (`v_tool_utilisation`): Utilization rankings (lifetime loans per physical unit).
   - **Audit Trail** (`audit_log`): Shows triggered change-log entries for loan and unit status modifications.

---

### Section 15: Concurrency Laboratory Demonstration (Estimated Duration: 2m 30s)

#### What to Click & Demonstrate:
1. Click the **"Concurrency lab"** tab in the top navigation.
2. Explain the purpose:
   - *"When two members click 'Reserve' for the last remaining unit at the exact same millisecond, what happens? Let's demonstrate race conditions and PostgreSQL concurrency solutions."*
3. Point out the simultaneous contenders setting (default: 2 threads).
4. Click **"Run all four"**.
5. Watch the four benchmark strategies execute live:
   - **Strategy 1 (Naive READ UNCOMMITTED / check-then-insert)**:
     - Outcome: Both threads see unit 1 as available, both execute INSERT.
     - Verdict: **`✗ DOUBLE-BOOKED - data corrupted`** (demonstrates the lost-update race anomaly!).
   - **Strategy 2 (Fix: Row Lock / SELECT ... FOR UPDATE)**:
     - Outcome: Thread 1 locks row; Thread 2 waits, then sees unit already Reserved.
     - Verdict: **`✓ exactly one booking - consistent`**.
   - **Strategy 3 (Fix: Isolation / SERIALIZABLE + retry)**:
     - Outcome: Thread 1 commits; Thread 2 detects serialization failure (40001) and retries cleanly.
     - Verdict: **`✓ exactly one booking - consistent`**.
   - **Strategy 4 (Fix: Declarative / UNIQUE(unit_id) constraint)**:
     - Outcome: Database engine enforces uniqueness; second insert rejected with `23505 unique_violation`.
     - Verdict: **`✓ exactly one booking - consistent`**.

---

### Section 16: Automated Test Suite Execution & Summary (Estimated Duration: 1m 30s)

#### What to Switch & Execute:
1. Switch to your terminal window alongside the browser.
2. Run the complete automated test suite:
   ```powershell
   python -m pytest tests -q
   ```
3. Show the output passing completely on screen:
   ```text
   ........................................................................ [ 93%]
   .....                                                                    [100%]
   77 passed in 30.12s
   ```
4. Conclude your video:
   - *"All 77 automated tests pass, verifying relational integrity, constraints, triggers, waitlist promotion, kit atomicity, concurrency safety, JWT authentication, and the responsive user interface."*
   - *"Thank you for watching the Library of Things system demonstration!"*

---

### Total Target Recording Time: ~20 to 22 minutes
*(Can easily be condensed to 10–12 minutes by moving smoothly between features).*
