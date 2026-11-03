"""Small local RBAC layer; replace the token store with an identity provider in production."""

from fastapi import Header, HTTPException

USERS = {
    "customer-demo": {"role": "customer"},
    "reviewer-demo": {"role": "reviewer"},
    "manager-demo": {"role": "manager"},
}


def current_user(x_user_id: str | None = Header(default=None)):
    if x_user_id not in USERS:
        raise HTTPException(status_code=401, detail="Use X-User-Id: reviewer-demo or customer-demo.")
    return {"id": x_user_id, **USERS[x_user_id]}


def require_role(user, *roles):
    if user["role"] not in roles:
        raise HTTPException(status_code=403, detail="This role cannot perform that action.")
