#!/usr/bin/env python3
from typing import List

from .influxclient import InfluxClient
from .influxtypes import Permission, Resource, TokenPost


class TokenMaker(InfluxClient):
    async def set_org_id(self) -> None:
        """Set the org id; requires org read permission in token"""
        url = f"{self.api_url}/orgs"
        obj = await self.get(url)
        orgs = obj["orgs"]
        for o in orgs:
            if o["name"] == self.org:
                self.org_id = o["id"]
                self.log.debug(f"Found OrgID: {self.org_id}")
                return
        raise RuntimeError(f"Could not determine orgID for org {self.org}")

    def define_token(self) -> TokenPost:
        perms: List[Permission] = []
        categories = (
            "buckets",
            "checks",
            "orgs",
            "tasks",
            "notificationRules",
            "notificationEndpoints",
        )
        for c in categories:
            for mode in ("read", "write"):
                perms.append(
                    Permission(
                        action=mode,
                        resource=Resource(orgID=self.org_id, type=c),
                    )
                )
        tok = TokenPost(
            description="Token for task/alert creation",
            orgID=self.org_id,
            permissions=perms,
        )
        self.log.debug(f"Token: {tok}")
        return tok

    async def create_token(self, tok):
        """Create an Authorization in InfluxDB."""
        url = f"{self.api_url}/authorizations"
        obj = await self.post(url, [tok])
        self.log.debug(f"token = {obj['token']}")

    async def main(self) -> None:
        await self.set_org_id()
        tok = self.define_token()
        await self.create_token(tok)
