#!/usr/bin/env python3
from dataclasses import asdict
from typing import Any, List

from .influxclient import InfluxClient
from .influxfns import get_template, seconds_to_duration_literal
from .influxtypes import (
    BucketGet,
    BucketPost,
    CheckPost,
    DashboardQuery,
    RetentionRule,
    TaskGet,
    TaskPost,
)


class RestartMapper(InfluxClient):
    """The logic needed to build alerts and tasks for applications."""

    async def list_buckets(self) -> List[BucketGet]:
        """List all buckets."""
        itemtype = "buckets"
        url = f"{self.api_url}/{itemtype}"
        b_list = await self.list_all(url, itemtype)
        buckets = [BucketGet(**x) for x in b_list]
        self.log.debug(f"Buckets -> {[x.name for x in buckets]}")
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

    async def construct_multiapp_bucket(self) -> None:
        buckets = await self.list_buckets()
        if not buckets:
            return
        await self.find_application_buckets(buckets)
        bnames = [x.name for x in buckets]
        if "multiapp_" in bnames:
            return
        self.log.debug("Constructing multiapp_ bucket")
        url = f"{self.api_url}/buckets"
        rr: List[RetentionRule] = [
            {
                "everySeconds": 3600,
                "shardGroupDurationSeconds": 3600,
                "type": "expire",
            }
        ]
        bkt = BucketPost(
            description="K8s multiple apps tracking bucket",
            name="multiapp_",
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
        task_template = get_template("restart")
        tasks = []
        offset = 0
        for app in apps:
            offset %= 60
            offsetstr = seconds_to_duration_literal(offset)
            taskname = f"{app.capitalize()} restarts"
            tasks.append(
                TaskPost(
                    description=taskname,
                    org=self.org,
                    orgID=self.org_id,
                    status="active",
                    flux=task_template.render(
                        taskname=taskname, app_bucket=app, offset=offsetstr
                    ),
                )
            )
            offset += 1
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
        check_template = get_template("check")
        check_flux = check_template.render()
        dq = DashboardQuery(name=cname, text=check_flux)
        ck = CheckPost(
            description=cname,
            every="1m",
            orgID=self.org_id,
            query=dq,
        )
        return ck

    async def main(self) -> None:
        await self.set_org_id()
        await self.construct_multiapp_bucket()
        await self.construct_tasks()
        # At the moment, building the check isn't working.
        # However the manual check/alerts are fine.
        # await self.construct_check()
