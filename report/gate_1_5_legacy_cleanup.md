# Gate 1.5 Summary — Legacy MVP Cleanup

**Date:** 2026-07-04  
**Status:** Complete

---

## User decision

The following legacy MVP DocTypes are removed and no longer required:

- Credit Account
- Credit Transaction
- Credit Management Settings

---

## Completed

- Removed MVP DocType source folders (`credit_account`, `credit_transaction`, `credit_management_settings`)
- Removed `utils/credit.py` direct balance mutation utility
- Cleared `install.after_install` MVP settings initialization (now no-op)
- Removed MVP desktop icons from `config/desktop.py`
- Replaced workspace with placeholder (no DocType shortcuts/links)
- Added idempotent cleanup patches and registered in `patches.txt`
- Fixed `table_exists()` usage and added follow-up `drop_mvp_tables` patch
- Executed patches on `jomveo` — DocTypes and tables removed
- Verified Gate 1 scaffold tests still pass (5/5)
- Updated `docs/decision_log.md`, `README.md`, `report/README.md`, `patches/v1_0/README.md`

---

## Files removed

| Path |
|---|
| `credit_management/credit_management/doctype/credit_account/` (entire folder) |
| `credit_management/credit_management/doctype/credit_transaction/` (entire folder) |
| `credit_management/credit_management/doctype/credit_management_settings/` (entire folder) |
| `credit_management/credit_management/utils/credit.py` |

---

## Files updated

| Path | Change |
|---|---|
| `credit_management/install.py` | No-op `after_install` |
| `credit_management/config/desktop.py` | Module icon only |
| `credit_management/credit_management/workspace/credit_management/credit_management.json` | Placeholder workspace |
| `credit_management/patches.txt` | Added cleanup patches |
| `credit_management/patches/v1_0/remove_mvp_doctypes.py` | New — MVP cleanup |
| `credit_management/patches/v1_0/drop_mvp_tables.py` | New — table drop fix |
| `patches/v1_0/README.md` | Documented cleanup |
| `docs/decision_log.md` | Gate 1.5 decisions D-013–D-018 |
| `README.md` | Gate 1.5 status |
| `report/README.md` | Gate 1.5 index entry |

---

## Patch added

| Patch | Purpose |
|---|---|
| `credit_management.patches.v1_0.remove_mvp_doctypes` | Delete MVP data, DocTypes, singles, workspace (if MVP present) |
| `credit_management.patches.v1_0.drop_mvp_tables` | Drop `tabCredit Account` / `tabCredit Transaction` (idempotent fix) |

---

## Database cleanup behavior

**DocType records removed:**
- `Credit Transaction`
- `Credit Account`
- `Credit Management Settings`

**Tables dropped:**
- `tabCredit Transaction`
- `tabCredit Account`

**Tables preserved:**
- None (no MVP tables retained)

**Reason:**
- MVP tables contained obsolete party/limit schema incompatible with production ledger model
- Dropping frees DocType names for Gate 2 recreation
- `drop_mvp_tables` patch added because initial patch used incorrect `table_exists("tab...")` call; corrected to `table_exists("Credit Account")`

**Workspace:**
- Old workspace with MVP links deleted by first patch
- Placeholder workspace re-synced from JSON (no DocType links)

---

## References search result

```bash
grep -R "Credit Transaction" -n credit_management || true
grep -R "Credit Management Settings" -n credit_management || true
grep -R "credit_transaction" -n credit_management || true
grep -R "credit_management_settings" -n credit_management || true
```

**Result:**

Remaining matches are **intentional only** in:
- `patches/v1_0/remove_mvp_doctypes.py` — cleanup patch source
- `patches/v1_0/README.md` — patch documentation
- `report/gate_0_discovery.md`, `report/gate_1_architecture_scaffold.md` — historical gate reports
- `docs/decision_log.md` — decision record

No matches in runtime code, DocType JSON, hooks, install, desktop, workspace links, or tests.

```bash
grep -R "utils/credit.py" -n credit_management || true
```

**Result:** Only historical references in gate reports and decision log. File deleted.

```bash
grep -R "Credit Account" -n credit_management || true
```

**Result:**

| Location | Status |
|---|---|
| `credit_management/api.py` (docstring) | **Intentional** — generic rule for future production model |
| `credit_management/api.py` (`reconcile_account(credit_account)`) | **Intentional** — parameter name, not MVP DocType |
| `patches/`, `report/`, `docs/decision_log.md` | **Historical/documentation** |

**No obsolete MVP implementation remains.**

---

## Tests run

```bash
bench --site jomveo migrate
bench --site jomveo run-tests --app credit_management
```

## Test result

* **Migrate:** Passed — both cleanup patches executed successfully
* **Unit tests:** **5 passed, 0 failed, 0 skipped**

```
.....
----------------------------------------------------------------------
Ran 5 tests in 0.001s

OK
```

---

## Risks or unresolved decisions

* **Historical gate reports** still mention MVP DocTypes — intentional audit trail; not current architecture docs
* **`drop_mvp_tables` follow-up patch** required due to initial `table_exists` bug — documented; both patches kept for fresh installs
* **Workspace is placeholder only** until Gate 2/6 adds production shortcuts
* **Gate 2 must create new `Credit Account`** — name is now free in DB and filesystem

---

## Next recommended gate

**Gate 2: Core Ledger**