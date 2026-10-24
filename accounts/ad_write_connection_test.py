
import os
import ssl

from ldap3 import Connection, Server, Tls, SIMPLE
from ldap3.core.exceptions import LDAPException

from accounts.ad_config import AD_SERVER, AD_PORT


def test_write_account_connection():
    username = os.getenv("AD_WRITE_BIND_USER", "")
    password = os.getenv("AD_WRITE_BIND_PASSWORD", "")

    if not username or not password:
        raise RuntimeError(
            "Set AD_WRITE_BIND_USER and AD_WRITE_BIND_PASSWORD first."
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
            user=username,
            password=password,
            authentication=SIMPLE,
            auto_bind=True,
            read_only=True,
            receive_timeout=10,
        )

        print("LDAPS authentication: successful")
        print("Bound account:", username)

    except LDAPException:
        print("LDAPS authentication failed. Check the account and password.")
        raise

    finally:
        if connection and connection.bound:
            connection.unbind()


if __name__ == "__main__":
    test_write_account_connection()
