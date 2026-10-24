
import os
import ssl
import secrets

from ldap3 import Connection, Server, Tls, SIMPLE

from accounts.ad_config import AD_SERVER, AD_PORT

TEST_OU = "OU=Django-Test-Users,DC=TEST,DC=local"


def run_test():
    username = os.getenv("AD_WRITE_BIND_USER", "")
    password = os.getenv("AD_WRITE_BIND_PASSWORD", "")

    if not username or not password:
        raise RuntimeError(
            "Write-account environment variables are missing."
        )

    test_username = "djt" + secrets.token_hex(4)
    user_dn = f"CN={test_username},{TEST_OU}"

    print("Test username:", test_username)
    print("Test DN:", user_dn)

    server = Server(
        AD_SERVER,
        port=AD_PORT,
        use_ssl=True,
        tls=Tls(validate=ssl.CERT_REQUIRED),
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
            read_only=False,
            receive_timeout=10,
        )

        print("LDAPS authentication: successful")
        print("LDAP server:", AD_SERVER, AD_PORT)
        print("Bind identity:", username)
        print("Target OU:", TEST_OU)

        attributes = {
            "sAMAccountName": test_username,
        }

        print("Attributes being sent:", list(attributes.keys()))

        created = connection.add(
            user_dn,
            object_class=[
                "top",
                "person",
                "organizationalPerson",
                "user",
            ],
            attributes=attributes,
        )

        if not created:
            print("User creation failed:", connection.result)
            return

        print("Temporary user object created:", user_dn)

        if connection.delete(user_dn):
            print("Temporary user deleted successfully.")
        else:
            print("CLEANUP REQUIRED. DN:", user_dn)
            print("Deletion result:", connection.result)

    finally:
        if connection and connection.bound:
            connection.unbind()


if __name__ == "__main__":
    run_test()
