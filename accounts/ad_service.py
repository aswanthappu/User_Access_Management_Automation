
import os
import ssl

from ldap3 import Connection, Server, Tls, SIMPLE, SUBTREE, MODIFY_REPLACE
from ldap3 import MODIFY_REPLACE
from accounts.ad_config import (
    AD_USER_CREATE_OU,
    AD_WRITE_BIND_USER,
    AD_WRITE_BIND_PASSWORD,
)

from ldap3 import Connection, Server, Tls, SIMPLE, SUBTREE
from accounts.ad_config import (
    AD_SERVER,
    AD_PORT,
    AD_BASE_DN,
    AD_BIND_USER,
    AD_BIND_PASSWORD,
)


def get_ad_connection():
    if not AD_BIND_USER or not AD_BIND_PASSWORD:
        raise RuntimeError("AD bind credentials are not configured.")

    tls = Tls(validate=ssl.CERT_REQUIRED)
    server = Server(
        AD_SERVER,
        port=AD_PORT,
        use_ssl=True,
        tls=tls,
        connect_timeout=5,
    )

    return Connection(
        server,
        user=AD_BIND_USER,
        password=AD_BIND_PASSWORD,
        authentication=SIMPLE,
        auto_bind=True,
        read_only=True,
        receive_timeout=10,
    )


def _value(entry, attribute):
    """Return an AD attribute as a string, or an empty string."""
    value = entry[attribute].value
    return "" if value is None else str(value)


def _user_details(entry):
    """Convert an LDAP user entry into a template-friendly dictionary."""
    account_control = entry["userAccountControl"].value
    disabled = (
        account_control is not None
        and bool(int(account_control) & 2)
    )

    return {
        "username": _value(entry, "sAMAccountName"),
        "display_name": _value(entry, "displayName"),
        "first_name": _value(entry, "givenName"),
        "last_name": _value(entry, "sn"),
        "email": _value(entry, "mail"),
        "department": _value(entry, "department"),
        "job_title": _value(entry, "title"),
        "description": _value(entry, "description"),
        "office": _value(entry, "physicalDeliveryOfficeName"),
        "phone": _value(entry, "telephoneNumber"),
        "distinguished_name": _value(entry, "distinguishedName"),
        "created": _value(entry, "whenCreated"),
        "last_logon": _value(entry, "lastLogonTimestamp"),
        "password_last_set": _value(entry, "pwdLastSet"),
        "is_disabled": disabled,
    }


def search_ad_users(search_term):
    """Search AD users by username, display name, or email."""
    if not search_term or not search_term.strip():
        return []

    term = search_term.strip()
    if len(term) > 100:
        raise ValueError("Search term is too long.")

    # Escape special LDAP filter characters.
    escaped = (
        term.replace("\\", r"\5c")
        .replace("*", r"\2a")
        .replace("(", r"\28")
        .replace(")", r"\29")
        .replace("\x00", r"\00")
    )

    search_filter = (
        "(&(objectCategory=person)(objectClass=user)"
        "(|(sAMAccountName=*{0}*)"
        "(displayName=*{0}*)"
        "(mail=*{0}*)))"
    ).format(escaped)

    connection = None

    try:
        connection = get_ad_connection()
        connection.search(
            search_base=AD_BASE_DN,
            search_filter=search_filter,
            search_scope=SUBTREE,
            attributes=[
                "sAMAccountName",
                "displayName",
                "givenName",
                "sn",
                "mail",
                "department",
                "title",
                "description",
                "physicalDeliveryOfficeName",
                "telephoneNumber",
                "userAccountControl",
                "distinguishedName",
                "whenCreated",
                "lastLogonTimestamp",
                "pwdLastSet",
            ],
            size_limit=50,
        )

        if connection.result.get("result") != 0:
            raise RuntimeError("Active Directory search failed.")

        return [_user_details(entry) for entry in connection.entries]

    finally:
        if connection and connection.bound:
            connection.unbind()

# Active Directory user-creation settings
AD_USER_CREATE_OU = "OU=Django-Test-Users,DC=TEST,DC=local"

# Separate credentials for delegated write operations.
# Set these using environment variables; do not hardcode passwords.
AD_WRITE_BIND_USER = os.getenv("AD_WRITE_BIND_USER", "")
AD_WRITE_BIND_PASSWORD = os.getenv("AD_WRITE_BIND_PASSWORD", "")




def create_ad_user(user_data):
    """Create an AD user in the configured OU using LDAPS."""
    import re
    import ssl

    if not AD_WRITE_BIND_USER or not AD_WRITE_BIND_PASSWORD:
        raise RuntimeError("AD write credentials are not configured.")

    username = user_data["username"].strip()

    if not re.fullmatch(r"[A-Za-z0-9._-]{1,20}", username):
        raise ValueError("Invalid AD username.")

    required_fields = ("first_name", "last_name", "display_name", "password")
    if any(not str(user_data.get(key, "")).strip() for key in required_fields):
        raise ValueError("Required AD user fields are missing.")

    user_dn = f"CN={username},{AD_USER_CREATE_OU}"

    server = Server(
        AD_SERVER,
        port=AD_PORT,
        use_ssl=True,
        tls=Tls(validate=ssl.CERT_REQUIRED),
        connect_timeout=5,
    )

    connection = None
    created = False

    try:
        connection = Connection(
            server,
            user=AD_WRITE_BIND_USER,
            password=AD_WRITE_BIND_PASSWORD,
            authentication=SIMPLE,
            auto_bind=True,
            read_only=False,
            receive_timeout=10,
        )

                # Check for duplicate usernames across the entire AD domain.
        connection.search(
            search_base=AD_BASE_DN,
            search_filter=(
                "(&(objectCategory=person)(objectClass=user)"
                f"(sAMAccountName={username}))"
            ),
            search_scope=SUBTREE,
            attributes=["sAMAccountName", "distinguishedName"],
            size_limit=2,
        )

        if connection.result.get("result") != 0:
            raise RuntimeError(
                f"AD duplicate check failed: {connection.result}"
            )

        if connection.entries:
            raise ValueError(
                f"Username '{username}' already exists in the target OU."
            )

        attributes = {
            "sAMAccountName": username,
            "userAccountControl": 514,  # Disabled normal account
            "givenName": user_data["first_name"].strip(),
            "sn": user_data["last_name"].strip(),
            "displayName": user_data["display_name"].strip(),
        }

        optional_attributes = {
            "mail": user_data.get("email", "").strip(),
            "department": user_data.get("department", "").strip(),
            "title": user_data.get("job_title", "").strip(),
            "description": user_data.get("description", "").strip(),
        }

        attributes.update({
            key: value
            for key, value in optional_attributes.items()
            if value
        })

        if not connection.add(
            user_dn,
            object_class=["top", "person", "organizationalPerson", "user"],
            attributes=attributes,
        ):
            raise RuntimeError(
                f"AD user creation failed: {connection.result}"
            )

        created = True

        # Set the initial password over LDAPS.
        encoded_password = (
            '"' + user_data["password"] + '"'
        ).encode("utf-16-le")

        if not connection.modify(
            user_dn,
            {
                "unicodePwd": [
                    (MODIFY_REPLACE, [encoded_password])
                ]
            },
        ):
            raise RuntimeError(
                f"User was created but password setup failed. "
                f"Inspect this disabled account: {user_dn}. "
                f"AD result: {connection.result}"
            )

        # Enable only after password setup succeeds.
        if not connection.modify(
            user_dn,
            {
                "userAccountControl": [
                    (MODIFY_REPLACE, [512])
                ]
            },
        ):
            raise RuntimeError(
                f"Password was set but account enabling failed. "
                f"Inspect account: {user_dn}. "
                f"AD result: {connection.result}"
            )

        return user_dn

    except Exception as exc:
        # Never include the submitted password in error messages.
        if created and not isinstance(exc, ValueError):
            raise RuntimeError(
                f"{exc} Account DN for administrator review: {user_dn}"
            ) from None
        raise

    finally:
        if connection and connection.bound:
            connection.unbind()
