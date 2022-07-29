from dataclasses import asdict
from typing import Dict, List, Union

from .influxclient import InfluxClient
from .influxfns import get_template, seconds_to_duration_literal
from .influxtypes import (
    BucketGet,
    BucketPost,
    RetentionRule,
    TaskGet,
    TaskPost,
)


class TaskMaker(InfluxClient):
    """The logic needed to build alerts and tasks for applications."""

    async def init_resources(self) -> None:
        self.timing: Dict[str, Dict[str, Union[str, bool]]] = {
            "restart": {
                "every": "5m",
                "offset": "30s",
                "app": True,
                "slack": True,
            },
            "disk_check": {
                "every": "5m",
                "offset": "56s",
                "app": False,
                "slack": True,
            },
            "state_check": {
                "every": "5m",
                "offset": "17s",
                "app": True,
                "slack": True,
            },
            "cpu_check": {
                "every": "5m",
                "offset": "43s",
                "app": True,
                "slack": True,
            },
        }
        # This is far too spammy, but leave it around so we remember
        #  how to reenable it.
        # "memory_check": {"every": "5m", "offset": "43s", "app": True},
        self.buckets = await self.list_buckets()
        app_buckets = await self.find_application_buckets(self.buckets)
        self.app_names = [x.name for x in app_buckets]
        self.extant_tasks: List[TaskGet] = []

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
        return app_buckets

    async def construct_multiapp_bucket(self) -> None:
        """Build the short-retention bucket for sending alerts"""
        bnames = [x.name for x in self.buckets]
        mn = "multiapp_"
        if mn in bnames:
            if not self.force:
                return
            # Delete the bucket, since force is set.
            bkt_id = ""
            for bkt in self.buckets:
                if bkt.name == mn:
                    bkt_id = bkt.id
                    break
            url = f"{self.api_url}/buckets/{bkt_id}"
            self.log.warning(f"Force is set: Deleting {mn} bucket ({bkt_id})")
            await self.delete(url)
        self.log.debug(f"Constructing {mn} bucket")
        url = f"{self.api_url}/buckets"
        rr: List[RetentionRule] = [
            {
                "everySeconds": 3600,
                "shardGroupDurationSeconds": 3600,
                "type": "expire",
            }
        ]
        bkt_p = BucketPost(
            description="K8s multiple apps tracking bucket",
            name=mn,
            orgID=self.org_id,
            retentionRules=rr,
        )
        payloads = [asdict(bkt_p)]
        await self.post(url, payloads)

    async def construct_tasks(self) -> None:
        """Make all tasks"""
        extant_tasks = await self.list_tasks()
        self.extant_tasks = extant_tasks
        self._extant_tnames = [x.name for x in extant_tasks]
        offset_mult = 0
        # If force is set, remove all tasks before proceeding
        if self.force:
            await self.delete_tasks()
        for k in self.timing:
            if self.timing[k]["slack"]:
                await self.construct_slack_task(k)
            if self.timing[k]["app"]:
                await self.construct_named_tasks(k)
            offset_mult += 1

    async def delete_tasks(self) -> None:
        """If self.force is set, remove existing tasks"""
        if not self.force:
            self.log.warning("Force is not set: refusing to delete tasks.")
            return
        for tsk in self.extant_tasks:
            tid = tsk.id
            tnm = tsk.name
            url = f"{self.api_url}/tasks/{tid}"
            self.log.warning(f"Force is set: deleting task {tnm} ({tid})")
            await self.delete(url)
        # Clear extant tasks/names, since they no longer exist
        self.extant_tasks = []
        self._extant_tnames = []

    async def construct_named_tasks(
        self, ttype: str, offset_mult: int = 0
    ) -> None:
        """Construct tasks for each app (if needed)"""
        apps_needing_tasks = [
            x
            for x in self.app_names
            if f"{x.capitalize()} {ttype}s" not in self._extant_tnames
        ]
        self.log.debug(f"Apps needing {ttype} tasks -> {apps_needing_tasks}")

        new_tasks = await self.build_tasks(
            apps_needing_tasks, ttype, offset_mult
        )
        payloads = [asdict(x) for x in new_tasks]
        url = f"{self.api_url}/tasks"
        await self.post(url, payloads)

    async def construct_slack_task(self, ttype: str) -> None:
        """Construct the Slack alerting tasks"""
        every = self.timing[ttype]["every"]
        offset = self.timing[ttype]["offset"]
        tname = f"_slack_notify_{ttype}s"
        if tname in self._extant_tnames:
            return
        task_template = get_template(ttype, template_marker="_slack.flux")
        task = TaskPost(
            description=tname,
            org=self.org,
            orgID=self.org_id,
            status="active",
            flux=task_template.render(
                offset=offset, every=every, taskname=tname
            ),
        )
        payload = [asdict(task)]
        url = f"{self.api_url}/tasks"
        await self.post(url, payload)

    async def build_tasks(
        self, apps: List[str], ttype: str, offset_mult: int = 0
    ) -> List[TaskPost]:
        """Create a list of task objects to post."""
        task_template = get_template(ttype, template_marker="_tmpl.flux")
        tasks = []
        offset = len(self.app_names) * offset_mult
        for app in apps:
            offset %= 60
            offsetstr = seconds_to_duration_literal(offset)
            if offsetstr == "infinite":
                offsetstr = "0s"
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
                        every="2m30s",
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
        """Construct any missing tasks"""
        await self.init_resources()
        await self.set_org_id()
        await self.construct_multiapp_bucket()
        await self.construct_tasks()
