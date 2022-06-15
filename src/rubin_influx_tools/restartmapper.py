#!/usr/bin/env python3
from dataclasses import asdict
from typing import Any, List

from .influxclient import InfluxClient
from .influxtypes import (
    BucketGet,
    BucketPost,
    CheckPost,
    DashboardQuery,
    RetentionRule,
    TaskGet,
    TaskPost,
)
from .tasktemplates import check_text, task_template


class RestartMapper(InfluxClient):
    """The logic needed to build alerts and tasks for applications."""

    async def set_org_id(self) -> None:
        """Set the Organization ID, given the Organization name.

        This doesn't actually work, even if you have r/w on orgs--you just
        get an empty list back.
        """
        url = f"{self.api_url}/orgs"
        obj = await self.get(url, use_session_params=False)
        orgs = obj["orgs"]
        for o in orgs:
            if o["name"] == self.org:
                self.org_id = o["id"]
                return
        raise RuntimeError(f"Could not determine orgID for org {self.org}")

    async def list_buckets(self) -> List[BucketGet]:
        """List all buckets."""
        itemtype = "buckets"
        url = f"{self.api_url}/{itemtype}"
        b_list = await self.list_all(url, itemtype)
        buckets = [BucketGet(**x) for x in b_list]
        self.log.debug(f"Buckets -> {[x.name for x in buckets]}")
        if buckets:
            # This is cheesy, but the orgs permissions don't work.
            self.org_id = buckets[0].orgID
        return buckets

    async def find_application_buckets(
        self, buckets: List[BucketGet]
    ) -> List[BucketGet]:
        """Any bucket whose name neither starts nor ends with an underscore is
        taken to be an application bucket.
        """
        app_buckets = [
            b for b in buckets if b.name[0] != "_" and b.name[-1] != "_"
        ]
        self.log.debug(f"App Buckets -> {[x.name for x in app_buckets]}")
        self.app_names = [x.name for x in app_buckets]
        return app_buckets

    async def construct_restarts_bucket(self) -> None:
        buckets = await self.list_buckets()
        if not buckets:
            return
        await self.find_application_buckets(buckets)
        bnames = [x.name for x in buckets]
        if "restarts_" in bnames:
            return
        self.log.debug("Constructing restarts_ bucket")
        url = f"{self.api_url}/buckets"
        rr: List[RetentionRule] = [
            {
                "everySeconds": 3600,
                "shardGroupDurationSeconds": 3600,
                "type": "expire",
            }
        ]
        bkt = BucketPost(
            description="K8s apps restart tracking bucket",
            name="restarts_",
            orgID=self.org_id,
            retentionRules=rr,
        )
        payloads = [asdict(bkt)]
        await self.post(url, payloads)

    async def construct_tasks(self) -> None:
        extant_tasks = await self.list_tasks()
        extant_tnames = [x.name for x in extant_tasks]
        apps_needing_tasks = [
            x
            for x in self.app_names
            if f"{x.capitalize()} restarts" not in extant_tnames
        ]
        self.log.debug(f"Apps needing tasks -> {apps_needing_tasks}")

        new_tasks = self.build_tasks(apps_needing_tasks)
        payloads = [asdict(x) for x in new_tasks]
        url = f"{self.api_url}/tasks"
        await self.post(url, payloads)

    def build_tasks(self, apps: List[str]) -> List[TaskPost]:
        """Create a list of task objects to post."""
        tasks = []
        for app in apps:
            taskname = f"{app.capitalize()} restarts"
            tasks.append(
                TaskPost(
                    description=taskname,
                    org=self.org,
                    orgID=self.org_id,
                    status="active",
                    flux=task_template.render(
                        taskname=taskname, app_bucket=app
                    ),
                )
            )
        return tasks

    async def list_tasks(self) -> List[TaskGet]:
        """List all tasks."""
        itemtype = "tasks"
        url = f"{self.api_url}/{itemtype}"
        pagesize = 100
        obj_list = await self.list_all(url, itemtype, pagesize=pagesize)
        tasks = [TaskGet(**x) for x in obj_list]
        self.log.debug(f"Tasks -> {[x for x in tasks]}")
        return tasks

    async def construct_check(self) -> List[Any]:
        self.check_id = ""
        cname = "K8s app restarts TEST"
        itemtype = "checks"
        url = f"{self.api_url}/{itemtype}"
        obj_list = await self.list_all_with_offset(url, itemtype)
        self.log.debug(f"Checks -> {obj_list}")
        resp = []
        for c in obj_list:
            if c["name"] == cname:
                self.check_id = c["id"]
                break
        if not self.check_id:
            cc = await self.create_check(cname)
            payloads = [asdict(cc)]
            resp = await self.post(url, payloads)
            # gives a 400 Bad Request right now.
        return resp

    async def create_check(self, cname: str) -> CheckPost:
        dq = DashboardQuery(name=cname, text=check_text)
        ck = CheckPost(
            description=cname,
            every="1m",
            orgID=self.org_id,
            query=dq,
        )
        return ck

    async def main(self) -> None:
        await self.construct_restarts_bucket()
        await self.construct_tasks()
        # At the moment, building the check isn't working.
        # However the manual check/alerts are fine.
        # await self.construct_check()
