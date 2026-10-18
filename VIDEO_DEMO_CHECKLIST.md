# VIDEO DEMONSTRATION RECORDING CHECKLIST
## Quick-Reference Sheet to Keep Open While Recording

Print or position this checklist beside your monitor during your recording session.

---

### Phase 1: Pre-Flight Check (Before Hitting "Record")
- [ ] PostgreSQL service is running (`localhost:5432`).
- [ ] Ran `python db/seed.py` for a clean demo state.
- [ ] Started backend: `python app/app.py` (listening at `http://localhost:5000`).
- [ ] Browser opened at `http://localhost:5000` (F11 fullscreen or clean window).
- [ ] Second terminal open and ready in project directory for running pytest.
- [ ] Desktop notifications muted and clutter minimized.
- [ ] Microphone tested and audio levels verified.

---

### Phase 2: Recording Steps (Follow in Order)

| # | Section | Key Action to Perform on Screen | Expected Visual Outcome |
|---|---|---|---|
| **1** | **Introduction** | Show landing page at `http://localhost:5000`. Point out "Library of Things" title and header branding. | Clean header, brand logo, Login/Register buttons. |
| **2** | **Landing Page** | Scroll hero, 8 feature cards, 3-step guide, and footer. | Professional UI, clear value proposition. |
| **3** | **Registration** | Click "Register". Demonstrate invalid email & 5-rule password checklist. Register `Priya Sharma` (`PriyaSecure2026!`). | Real-time validation checks; green success toast; auto-redirect to login. |
| **4** | **Auth & Role Boundary** | Log in as Priya (`member`). Show tabs. Log out. Try logging in as Priya with role "Admin". | Priya rejected from Admin role with red card: *"Account does not have administrator privileges"*. |
| **5** | **Catalogue & Reserve** | Sign in as `Aarav Kumar · member`. Search "saw", click category chips. Click "Units" on Drill. Reserve a "Jigsaw". | Category filtering; physical units modal; green toast with reservation confirmation. |
| **6** | **Waitlist Join** | Filter by "Garden & Outdoor". Click "Join waitlist" on Pressure Washer (`all out`). | Green toast: *"All units out - you are #1 on the waitlist"*. |
| **7** | **Kits (Member view)** | Click "Kits". Show Home Renovation Kit (`Blocked by Tile Cutter`). Show Weekend Camping Kit (`Available`). | Clear visual explanation of atomic kit rules. |
| **8** | **My Account** | Click "My account". Show Notifications, Waitlist position #1, active Jigsaw reservation, loan history. | Member account hub and cancel action. |
| **9** | **Staff Checkout** | Sign in as `Staff Meena · staff`. Go to Staff desk → "Reservations to collect". Click "Hand over". | Reservation fulfilled; loan created. |
| **10**| **Waitlist Cascade** | Go to "Open loans". Click "Return…" on Pressure Washer. Condition: "No damage". | **Cascade fires!** Toast: *"Aarav Kumar promoted to Pressure Washer #1"*. |
| **11**| **Damage & Repair** | Go to "Open loans". Click "Return…" on Cordless Drill. Severity: "Major". Notes: "Chuck cracked". | Unit flips to `Repair`. Show "Repair bench". Click "Repair done" → back to `Available`. |
| **12**| **Guarded Deposit** | Go to "Deposits". Click "Release" on a loan whose return window is still open. | Stored procedure error toast: *"return window open until..."*. |
| **13**| **Atomic Kit Checkout**| Go to "Kits". Attempt checkout on blocked Home Renovation Kit (fails safely). Check out Weekend Camping Kit. | Red failure toast for blocked kit; green toast (*"Kit checked out: 4 loans"*) for free kit. |
| **14**| **Dashboard** | Click "Dashboard". Tour KPI cards, live fleet status bar, overdue loans, utilization, and audit log. | Real-time analytics computed directly from PostgreSQL views. |
| **15**| **Concurrency Lab** | Click "Concurrency lab". Click "Run all four". Compare Naive race (double-booked!) vs 3 fixes. | Clear side-by-side terminal-style output demonstrating database race conditions & fixes. |
| **16**| **Test Suite** | Switch to terminal. Run `python -m pytest tests -q`. | **77 passed** displayed live in terminal. |

---

### Phase 3: Post-Recording Wrap Up
- [ ] Stop screen recording.
- [ ] Stop Flask server: Press `Ctrl + C` in the app terminal.
- [ ] (Optional) Run `python db/seed.py` if you wish to reset demo data for another take.
