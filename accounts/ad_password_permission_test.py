
import os
import ssl
import secrets

from ldap3 import (
    Connection,
    Server,
    Tls,
    SIMPLE,
    MODIFY_REPLACE,
)

from accounts.ad_config import AD_SERVER, AD_PORT

TEST_OU = "OU=Django-Test-Users,DC=TEST,DC=local"


def run_test():
    username = os.getenv("AD_WRITE_BIND_USER", "")
    password = os.getenv("AD_WRITE_BIND_PASSWORD", "")

    if not username or not password:
        raise RuntimeError("Write-account environment variables are missing.")

    test_username = "dju" + secrets.token_hex(4)
    user_dn = f"CN={test_username},{TEST_OU}"
    temporary_password = "T9!" + secrets.token_urlsafe(16) + "aA1"

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
            user=username,
            password=password,
            authentication=SIMPLE,
            auto_bind=True,
            read_only=False,
            receive_timeout=10,
        )

        print("LDAPS authentication: successful")
        print("Test username:", test_username)

        created = connection.add(
            user_dn,
            object_class=[
                "top",
                "person",
                "organizationalPerson",
                "user",
            ],
            attributes={
                "sAMAccountName": test_username,
                "userAccountControl": 514,
            },
        )

        if not created:
            print("User creation failed:", connection.result)
            return

        print("Disabled test account created.")

        encoded_password = (
            '"' + temporary_password + '"'
        ).encode("utf-16-le")

        if not connection.modify(
            user_dn,
            {
                "unicodePwd": [
                    (MODIFY_REPLACE, [encoded_password])
                ]
            },
        ):
            print("Password setting failed:", connection.result)
            return

        print("Initial password set successfully.")

        if connection.modify(
            user_dn,
            {"userAccountControl": [(MODIFY_REPLACE, [512])]},
        ):
            print("Account enabled successfully.")
        else:
            print("Account enabling failed:", connection.result)

    except Exception as exc:
        print("Test error:", type(exc).__name__, str(exc))

    finally:
        if connection and connection.bound:
            connection.unbind()

    if created:
        print("Temporary account DN:", user_dn)
        print("Remove this test account using an AD administrator.")


if __name__ == "__main__":
    run_test()
