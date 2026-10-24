
import ssl

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
