#!/usr/bin/env python3
from dataclasses import asdict
from typing import List

from .influxclient import InfluxClient
from .influxtypes import Permission, Resource, TokenPost


class TokenMaker(InfluxClient):
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

    async def create_token(self, tok: TokenPost) -> None:
        """Create an Authorization in InfluxDB."""
        url = f"{self.api_url}/authorizations"
        obj = await self.post(url, [asdict(tok)])
        self.log.debug(f"token = {obj[0]['token']}")

    async def main(self) -> None:
        await self.set_org_id()
        tok = self.define_token()
        await self.create_token(tok)
