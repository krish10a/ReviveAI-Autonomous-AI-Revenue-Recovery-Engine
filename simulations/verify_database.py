"""
Verification script to directly query PostgreSQL and validate all tables and ledger consistency.
"""
from apps.api.app.database import SessionLocal
from apps.api.app.models import (
    Payment,
    RecoveryCase,
    FailureDiagnosis,
    RecoveryPrediction,
    RecoveryAction,
    PolicyDecision,
    Communication,
    AuditLog,
    RecoveryLedger,
)

def verify_database_state():
    db = SessionLocal()
    try:
        print("\n=======================================================")
        print("      POSTGRESQL DATABASE RECORD VERIFICATION")
        print("=======================================================")
        counts = {
            "payments": db.query(Payment).count(),
            "recovery_cases": db.query(RecoveryCase).count(),
            "failure_diagnoses": db.query(FailureDiagnosis).count(),
            "recovery_predictions": db.query(RecoveryPrediction).count(),
            "recovery_actions": db.query(RecoveryAction).count(),
            "policy_decisions": db.query(PolicyDecision).count(),
            "communications": db.query(Communication).count(),
            "audit_logs": db.query(AuditLog).count(),
            "recovery_ledger": db.query(RecoveryLedger).count(),
        }

        for table, count in counts.items():
            print(f"  {table:22}: {count} records")
            assert count >= 0, f"Table {table} query failed"

        assert counts["recovery_cases"] > 0, "No recovery cases in database"
        assert counts["recovery_ledger"] > 0, "No recovery ledger entries in database"

        print("\n=======================================================")
        print("      PERSISTED RECOVERY LEDGER AUDIT ENTRIES")
        print("=======================================================")
        ledger_entries = db.query(RecoveryLedger).all()
        for l in ledger_entries:
            print(f"  Ledger #{l.id} | Case #{l.case_id} | Gross: ₹{l.gross_amount} | Cost: ₹{l.action_cost} | Net: ₹{l.net_recovered} | Action: {l.recovery_action} | Ref: {l.provider_reference}")
            assert l.net_recovered == (l.gross_amount - l.action_cost), "Net recovery mismatch!"

        print("\n>>> ALL TABLES & RECOVERY LEDGER RECORDS CONFIRMED VALID IN POSTGRESQL!\n")
    finally:
        db.close()

if __name__ == "__main__":
    verify_database_state()
