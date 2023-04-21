from linode_api4.errors import UnexpectedResponseError
from linode_api4.objects import Base, Property


class AuthorizedApp(Base):
    api_endpoint = "/profile/apps/{id}"

    properties = {
        "id": Property(identifier=True),
        "scopes": Property(),
        "label": Property(),
        "created": Property(is_datetime=True),
        "expiry": Property(is_datetime=True),
        "thumbnail_url": Property(),
        "website": Property(),
    }


class PersonalAccessToken(Base):
    api_endpoint = "/profile/tokens/{id}"

    properties = {
        "id": Property(identifier=True),
        "scopes": Property(),
        "label": Property(mutable=True),
        "created": Property(is_datetime=True),
        "token": Property(),
        "expiry": Property(is_datetime=True),
    }


class WhitelistEntry(Base):
    api_endpoint = "/profile/whitelist/{id}"

    properties = {
        "id": Property(identifier=True),
        "address": Property(),
        "netmask": Property(),
        "note": Property(),
    }


class Profile(Base):
    api_endpoint = "/profile"
    id_attribute = "username"

    properties = {
        "username": Property(identifier=True),
        "uid": Property(),
        "email": Property(mutable=True),
        "timezone": Property(mutable=True),
        "email_notifications": Property(mutable=True),
        "referrals": Property(),
        "ip_whitelist_enabled": Property(mutable=True),
        "lish_auth_method": Property(mutable=True),
        "authorized_keys": Property(mutable=True),
        "two_factor_auth": Property(),
        "restricted": Property(),
        "authentication_type": Property(),
        "authorized_keys": Property(),
        "verified_phone_number": Property(),
    }

    def enable_tfa(self):
        """
        Enables TFA for the token's user.  This requies a follow-up request
        to confirm TFA.  Returns the TFA secret that needs to be confirmed.
        """
        result = self._client.post("/profile/tfa-enable")

        return result["secret"]

    def confirm_tfa(self, code):
        """
        Confirms TFA for an account.  Needs a TFA code generated by enable_tfa
        """
        self._client.post(
            "/profile/tfa-enable-confirm", data={"tfa_code": code}
        )

        return True

    def disable_tfa(self):
        """
        Turns off TFA for this user's account.
        """
        self._client.post("/profile/tfa-disable")

        return True

    @property
    def grants(self):
        """
        Returns grants for the current user
        """
        from linode_api4.objects.account import (  # pylint: disable-all
            UserGrants,
        )

        resp = self._client.get(
            "/profile/grants"
        )  # use special endpoint for restricted users

        grants = None
        if resp is not None:
            # if resp is None, we're unrestricted and do not have grants
            grants = UserGrants(self._client, self.username, resp)

        return grants

    @property
    def whitelist(self):
        """
        Returns the user's whitelist entries, if whitelist is enabled
        """
        return self._client._get_and_filter(WhitelistEntry)

    def add_whitelist_entry(self, address, netmask, note=None):
        """
        Adds a new entry to this user's IP whitelist, if enabled
        """
        result = self._client.post(
            "{}/whitelist".format(Profile.api_endpoint),
            data={
                "address": address,
                "netmask": netmask,
                "note": note,
            },
        )

        if not "id" in result:
            raise UnexpectedResponseError(
                "Unexpected response creating whitelist entry!"
            )

        return WhitelistEntry(result["id"], self._client, json=result)


class SSHKey(Base):
    """
    An SSH Public Key uploaded to your profile for use in Linode Instance deployments.
    """

    api_endpoint = "/profile/sshkeys/{id}"

    properties = {
        "id": Property(identifier=True),
        "label": Property(mutable=True),
        "ssh_key": Property(),
        "created": Property(is_datetime=True),
    }


class TrustedDevice(Base):
    api_endpoint = "/profile/devices/{id}"

    properties = {
        "id": Property(identifier=True),
        "created": Property(is_datetime=True),
        "expiry": Property(is_datetime=True),
        "last_authenticated": Property(is_datetime=True),
        "last_remote_addr": Property(),
        "user_agent": Property(),
    }


class ProfileLogin(Base):
    api_endpoint = "profile/logins/{id}"

    properties = {
        "id": Property(identifier=True),
        "datetime": Property(is_datetime=True),
        "ip": Property(),
        "restricted": Property(),
        "status": Property(),
        "username": Property(),
    }
