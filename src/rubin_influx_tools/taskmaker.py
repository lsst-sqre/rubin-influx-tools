import datetime
import os
from dataclasses import asdict
from typing import Any, Dict, List, Union

import yaml

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
        # We want to explode if we can't read the variable anyway.
        self.webhooks = yaml.safe_load(os.environ["WEBHOOKS_YAML"])
        self.buckets = await self.list_buckets()
        webhook_bkt = await self.find_webhook_bucket()
        if webhook_bkt:
            await self.destroy_webhooks_bucket(webhook_bkt)
        await self.construct_webhooks_bucket()
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

    async def find_webhook_bucket(self) -> BucketGet | None:
        """Return 'webhooks_' bucket if found."""
        for bk in self.buckets:
            # We rebuild webhooks_ each time, in case the list has changed.
            if bk.name == "webhooks_":
                return bk
        return None

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

    async def destroy_webhooks_bucket(self, bkt: BucketGet) -> None:
        """Destroy the webhooks_ bucket"""
        url = f"{self.api_url}/buckets/{bkt.id}"
        self.log.info(f"Deleting 'webhooks_' bucket ({bkt.id})")
        await self.delete(url)

    async def construct_webhooks_bucket(self) -> None:
        """Build the bucket containing webhook destinations"""
        rr: List[RetentionRule] = [
            {
                "everySeconds": 0,  # Keep forever
                "type": "expire",
            }
        ]
        bkt_p = BucketPost(
            description="Webhook channel destinations",
            name="webhooks_",
            orgID=self.org_id,
            retentionRules=rr,
        )
        payload = [asdict(bkt_p)]
        self.log.info("Constructing 'webhooks_' bucket")
        url = f"{self.api_url}/buckets"
        await self.post(url, payload)
        self.buckets = await self.list_buckets()
        webhook_bkt = await self.find_webhook_bucket()
        if webhook_bkt is None:
            raise RuntimeError("No 'webhooks_' bucket found after creation")
        await self.populate_webhooks(webhook_bkt)

    async def populate_webhooks(self, bkt: BucketGet) -> None:
        lp_str = ""
        now = int(
            1e9 * datetime.datetime.now(datetime.timezone.utc).timestamp()
        )
        for webhook in self.webhooks:
            url = webhook["webhook_url"]
            channel = (
                webhook["channel"][1:]
                if webhook["channel"].startswith("#")
                else webhook["channel"]
            )
            cluster = (
                webhook["phalanx_host"]
                if webhook["phalanx_host"]
                else (
                    channel[7:] if channel.startswith("status-") else channel
                )
            )
            lp_str += (
                f"webhook,channel={channel},cluster={cluster}"
                f' url="{url}" {now}\n'
            )
        # Note we have to go through self.session.post and mess with
        # the session headers, because the data write isn't JSON
        write_url = f"{self.api_url}/write"
        self.session.headers.update({"Content-Type": "text/plain"})
        self.log.debug(f"Writing line protocol:\n----\n{lp_str}\n----\n")
        await self.session.post(
            write_url,
            data=lp_str,
            params={"org": self.org, "bucket": bkt.id},
        )
        # Restore correct Content-Type for everything else.
        self.session.headers.update({"Content-Type": "application/json"})

    async def construct_ephemeral_buckets(self) -> None:
        """Build the short-retention buckets for alerting"""
        bnames = [x.name for x in self.buckets]
        ebnames = ["multiapp_", "alerted_"]
        payloads: List[Dict[str, Any]] = []
        for mn in ebnames:
            if mn in bnames and self.force:
                # Delete the bucket, since force is set.
                bkt_id = ""
                for bkt in self.buckets:
                    if bkt.name == mn:
                        bkt_id = bkt.id
                        break
                url = f"{self.api_url}/buckets/{bkt_id}"
                self.log.warning(
                    f"Force is set: Deleting {mn} bucket ({bkt_id})"
                )
                await self.delete(url)
            if mn not in bnames or self.force:
                self.log.debug(f"Constructing {mn} bucket")
                url = f"{self.api_url}/buckets"
                # One hour is the shortest expiration allowed.
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
                payloads.append(asdict(bkt_p))

        if payloads:
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
        await self.set_org_id()
        await self.init_resources()
        await self.construct_ephemeral_buckets()
        await self.construct_tasks()
