import glob
import tempfile
from dataclasses import asdict
from os.path import join
from typing import List, Set

import yaml
from git import Repo

from .influxclient import InfluxClient
from .influxtypes import BucketGet, BucketPost, RetentionRule

PHALANX = "https://github.com/lsst-sqre/phalanx.git"
# ANCILLARY does not include "multiapp_" because it has a different retention
# policy and is made in taskmaker.
# "argocd" is implicit everywhere.
ANCILLARY = ["argocd", "roundtable_internal_", "roundtable_prometheus_"]


class BucketMaker(InfluxClient):
    async def make_all_buckets(self) -> None:
        app_set = await self.check_phalanx()
        for app in ANCILLARY:
            app_set.add(app)
        self.log.debug(f"Required buckets -> {app_set}")
        extant_bkts = await self.list_buckets()
        ebnames = [x.name for x in extant_bkts]
        self.log.debug(f"Extant Buckets -> {ebnames}")
        needed = [x for x in app_set if x not in ebnames]
        self.log.debug(f"Needed Buckets -> {needed}")
        await self.create_needed_buckets(needed)

    async def check_phalanx(self) -> Set[str]:
        with tempfile.TemporaryDirectory() as td:
            _ = Repo.clone_from(PHALANX, td)
            pathname = join(td, "science-platform", "*.yaml")
            yamls = glob.glob(pathname)
            enabled = set()
            for yml in yamls:
                with open(yml, "r") as f:
                    ydoc = yaml.safe_load(f)
                    self.log.debug(f"{yml} -> {ydoc}")
                    for yk in ydoc:
                        obj = ydoc[yk]
                        # If the top-level key is itself an object, and if
                        # that object has an "enabled" field, and that field
                        # is truthy, that key represents an enabled Phalanx
                        # application.
                        if type(obj) is dict:
                            if obj.get("enabled"):
                                enabled.add(yk.replace("-", "_"))
            return enabled

    async def list_buckets(self) -> List[BucketGet]:
        """List all buckets."""
        itemtype = "buckets"
        url = f"{self.api_url}/{itemtype}"
        b_list = await self.list_all(url, itemtype)
        buckets = [BucketGet(**x) for x in b_list]
        self.log.debug(f"Buckets -> {buckets}")
        return buckets

    async def create_needed_buckets(self, needed: List[str]) -> None:
        for nd in needed:
            self.log.debug(f"Constructing {nd} bucket")
            url = f"{self.api_url}/buckets"
            rr: List[RetentionRule] = [
                {
                    "everySeconds": 604800,
                    "shardGroupDurationSeconds": 604800,
                    "type": "expire",
                }
            ]
            bkt = BucketPost(
                description=f"{nd} K8s metrics",
                name=nd,
                orgID=self.org_id,
                retentionRules=rr,
            )
            payloads = [asdict(bkt)]
            await self.post(url, payloads)

    async def main(self) -> None:
        await self.set_org_id()
        await self.make_all_buckets()
