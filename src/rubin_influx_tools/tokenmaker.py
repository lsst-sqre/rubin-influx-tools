from dataclasses import asdict
from typing import List

from .influxclient import InfluxClient
from .influxtypes import Permission, Resource, TokenPost


class TokenMaker(InfluxClient):
    def define_tokens(self) -> List[TokenPost]:
        tele_tok = self.define_telegraf_token()
        task_tok = self.define_task_token()
        return [tele_tok, task_tok]

    def define_telegraf_token(self) -> TokenPost:
        perms: List[Permission] = [
            Permission(
                action="write",
                resource=Resource(type="buckets"),
            )
        ]
        tok = TokenPost(
            description="Token for remote telegraf bucket writing",
            orgID=self.org_id,
            permissions=perms,
        )
        self.log.debug(f"Token: {tok}")
        return tok

    def define_task_token(self) -> TokenPost:
        perms: List[Permission] = []
        categories = (
            "buckets",
            "orgs",
            "tasks",
        )
        for c in categories:
            for mode in ("read", "write"):
                perms.append(
                    Permission(
                        action=mode,
                        resource=Resource(type=c),
                    )
                )
        tok = TokenPost(
            description="Token for task/alert creation",
            orgID=self.org_id,
            permissions=perms,
        )
        self.log.debug(f"Token: {tok}")
        return tok

    async def create_tokens(self) -> None:
        """Create an Authorization in InfluxDB."""
        url = f"{self.api_url}/authorizations"
        tele_tok = self.define_telegraf_token()
        task_tok = self.define_task_token()
        resps = await self.post(url, [asdict(tele_tok), asdict(task_tok)])
        for rsp in resps:
            obj = await rsp.json()
            desc = obj["description"]
            token = obj["token"]
            self.log.info(f"{desc}: {token}")

    async def main(self) -> None:
        await self.set_org_id()
        await self.create_tokens()
