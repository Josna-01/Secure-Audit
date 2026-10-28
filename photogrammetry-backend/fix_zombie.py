from sqlalchemy import text
from db import SessionLocal

JOB_ID = "a66f9e2c-8902-4646-b210-f3c7301a8bc7"
MSG = "Pipeline thread terminated unexpectedly during COLMAP reconstruction (step 4). Job was stuck in Processing state."

db = SessionLocal()
result = db.execute(
    text(
        "UPDATE photogrammetry_models "
        "SET status='Failed', error_message=:msg, completed_at=now() "
        "WHERE id=cast(:jid as uuid) AND status='Processing'"
    ),
    {"jid": JOB_ID, "msg": MSG}
)
db.commit()
db.close()
print(f"Rows updated: {result.rowcount}")
