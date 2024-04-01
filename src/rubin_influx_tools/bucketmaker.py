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
ANCILLARY = ["argocd"]


class BucketMaker(InfluxClient):
    async def make_all_buckets(self) -> None:
        """Create all of our buckets"""
        app_set = await self.check_phalanx()
        for app in ANCILLARY:
            app_set.add(app)
        self.log.debug(f"Required buckets -> {app_set}")
        extant_bkts = await self.list_buckets()
        ebnames = [x.name for x in extant_bkts]
        self.log.debug(f"Extant Buckets -> {ebnames}")
        if self.force:
            # remove all of our buckets.
            await self.delete_buckets(app_set, extant_bkts)
            ebnames = []
        needed = [x for x in app_set if x not in ebnames]
        self.log.debug(f"Needed Buckets -> {needed}")
        await self.create_needed_buckets(needed)

    async def delete_buckets(
        self, app_set: Set[str], extant_bkts: List[BucketGet]
    ) -> None:
        """Remove all of our buckets, if self.force is set"""
        if not self.force:
            self.log.warning("Force is not set: refusing to delete buckets")
            return
        to_remove = []
        for bkt in extant_bkts:
            if bkt.name in app_set:
                to_remove.append(bkt)
        for bkt in to_remove:
            url = "{self.api_url}/buckets/{bkt.id}"
            self.log.warning(f"Removing bucket {bkt.name} ({bkt.id})")
            await self.delete(url)

    async def check_phalanx(self) -> Set[str]:
        """Determine (from phalanx config) which applications are active"""
        with tempfile.TemporaryDirectory() as td:
            _ = Repo.clone_from(PHALANX, td)
            pathname = join(td, "environments", "*.yaml")
            yamls = glob.glob(pathname)
            enabled = set()
            for yml in yamls:
                with open(yml, "r") as f:
                    ydoc = yaml.safe_load(f)
                    # The applications are under the "applications" key.
                    # But Chart.yaml doesn't have one of those.
                    apps = ydoc.get("applications", {})
                    self.log.debug(f"{yml} applications -> {apps}")
                    for app in apps:
                        # The value will be true if the application is
                        # enabled.
                        if app:
                            enabled.add(app.replace("-", "_"))
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
        """Create any buckets that do not yet exist"""
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
        """Make any missing buckets"""
        await self.set_org_id()
        await self.make_all_buckets()
