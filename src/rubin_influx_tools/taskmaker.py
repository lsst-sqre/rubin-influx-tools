#!/usr/bin/env python3
from dataclasses import asdict
from typing import List

from .influxclient import InfluxClient
from .influxfns import get_template, seconds_to_duration_literal
from .influxtypes import (
    BucketGet,
    BucketPost,
    RetentionRule,
    TaskGet,
    TaskPost,
)

slack_timing = {
    "restart": {"every": "1m", "offset": "30s"},
    "memory_check": {"every": "5m", "offset": "43s"},
}


class TaskMaker(InfluxClient):
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
        self._extant_tnames = [x.name for x in extant_tasks]

        for ttype in "restart", "memory_check":
            await self.construct_named_tasks(ttype)
            await self.construct_slack_task(ttype)

    async def construct_named_tasks(self, ttype: str) -> None:
        apps_needing_tasks = [
            x
            for x in self.app_names
            if f"{x.capitalize()} {ttype}s" not in self._extant_tnames
        ]
        self.log.debug(f"Apps needing {ttype} tasks -> {apps_needing_tasks}")

        new_tasks = await self.build_tasks(apps_needing_tasks, ttype)
        payloads = [asdict(x) for x in new_tasks]
        url = f"{self.api_url}/tasks"
        await self.post(url, payloads)

    async def construct_slack_task(self, ttype: str) -> None:
        every = slack_timing[ttype]["every"]
        offset = slack_timing[ttype]["offset"]
        tname = f"_slack_notify_{ttype}s"
        if tname in self._extant_tnames:
            return
        task_text = get_template(ttype, template_marker="_slack.flux")
        task = TaskPost(
            description=tname,
            org=self.org,
            orgID=self.org_id,
            status="active",
            flux=task_text.render(offset=offset, every=every, taskname=tname),
        )
        payload = [asdict(task)]
        url = f"{self.api_url}/tasks"
        await self.post(url, payload)

    async def build_tasks(self, apps: List[str], ttype: str) -> List[TaskPost]:
        """Create a list of task objects to post."""
        task_template = get_template(ttype)
        tasks = []
        offset = 0
        for app in apps:
            offset %= 60
            offsetstr = seconds_to_duration_literal(offset)
            taskname = f"{app.capitalize()} {ttype}s"
            tasks.append(
                TaskPost(
                    description=taskname,
                    org=self.org,
                    orgID=self.org_id,
                    status="active",
                    flux=task_template.render(
                        taskname=taskname,
                        app_bucket=app,
                        offset=offsetstr,
                        every="1m",
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

    async def main(self) -> None:
        await self.set_org_id()
        await self.construct_multiapp_bucket()
        await self.construct_tasks()
        # At the moment, building the check isn't working.
        # However the manual check/alerts are fine.
        # await self.construct_check()
