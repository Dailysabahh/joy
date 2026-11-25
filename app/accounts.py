"""Website accounts for people who save a voice agent."""
import re
from datetime import datetime, timedelta, timezone

from database.models import CustomerAccount, User

COOKIE = "closer_portal"
_NAME = re.compile(r"[a-z0-9_]{3,24}")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def account_from_request(request, db) -> CustomerAccount | None:
    token = request.cookies.get(COOKIE) or request.query_params.get("token")
    if not token:
        return None
    return db.query(CustomerAccount).filter(CustomerAccount.portal_token == token).first()


def register(db, username: str, password: str, email: str, confirm: str) -> CustomerAccount:
    username = (username or "").strip().lower()
    email = (email or "").strip().lower()
    if not _NAME.fullmatch(username):
        raise ValueError("Use 3 to 24 letters, numbers, or underscores.")
    if not _EMAIL.fullmatch(email):
        raise ValueError("Enter the email the verification should go to.")
    if len(password or "") < 6:
        raise ValueError("Password needs at least 6 characters.")
    if password != confirm:
        raise ValueError("The two passwords do not match.")
    if db.query(CustomerAccount).filter(CustomerAccount.username == username).first():
        raise ValueError("That username is already taken.")
    if db.query(CustomerAccount).filter(CustomerAccount.email == email).first():
        raise ValueError("That email is already used.")
    user = User(phone=f"studio:{username}", name=username, state="studio")
    db.add(user)
    db.flush()
    account = CustomerAccount(
        user_id=user.id,
        username=username,
        email=email,
        email_verified=False,
        password_hash=CustomerAccount.hash_password(password),
        plan="none",
        access="new",
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def start_trial(db, account: CustomerAccount, selected_plan: str) -> CustomerAccount:
    plans = {"starter", "growth", "enterprise"}
    account.plan = selected_plan if selected_plan in plans else "starter"
    account.access = "trial"
    account.trial_ends_at = datetime.now(timezone.utc) + timedelta(days=3)
    db.commit()
    db.refresh(account)
    return account


def trial_open(account: CustomerAccount) -> bool:
    if (account.access or "") != "trial":
        return False
    ends = account.trial_ends_at
    if not ends:
        return False
    if ends.tzinfo is None:
        ends = ends.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) < ends


def can_integrate(account: CustomerAccount) -> bool:
    return (account.access or "paid") == "paid"


def days_left(account: CustomerAccount) -> int:
    ends = account.trial_ends_at
    if not ends:
        return 0
    if ends.tzinfo is None:
        ends = ends.replace(tzinfo=timezone.utc)
    remaining = ends - datetime.now(timezone.utc)
    return max(0, remaining.days + (1 if remaining.seconds else 0))
