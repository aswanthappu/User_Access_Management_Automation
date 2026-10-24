
import ssl

from ldap3 import (
    Connection,
    Server,
    Tls,
    SIMPLE,
    SUBTREE,
)
from ldap3.core.exceptions import LDAPException

from accounts.ad_config import (
    AD_SERVER,
    AD_PORT,
    AD_BASE_DN,
    AD_BIND_USER,
    AD_BIND_PASSWORD,
)


def test_ad_connection():
    if not AD_BIND_USER or not AD_BIND_PASSWORD:
        raise RuntimeError(
            "Set AD_BIND_USER and AD_BIND_PASSWORD first."
        )

    tls = Tls(validate=ssl.CERT_REQUIRED)

    server = Server(
        AD_SERVER,
        port=AD_PORT,
        use_ssl=True,
        tls=tls,
        connect_timeout=5,
    )

    connection = None

    try:
        connection = Connection(
            server,
            user=AD_BIND_USER,
            password=AD_BIND_PASSWORD,
            authentication=SIMPLE,
            auto_bind=True,
            read_only=True,
            receive_timeout=10,
        )

        connection.search(
            search_base=AD_BASE_DN,
            search_filter="(objectClass=domain)",
            search_scope=SUBTREE,
            attributes=["distinguishedName"],
            size_limit=1,
        )

        print("LDAP bind: successful")
        print("Search result:", connection.result)
        print("Entries returned:", len(connection.entries))

    except LDAPException as exc:
        print("LDAP connection failed:", exc)
        raise

    finally:
        if connection and connection.bound:
            connection.unbind()


if __name__ == "__main__":
    test_ad_connection()
