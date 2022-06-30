from dataclasses import asdict
from typing import Any, Dict, List

from .influxclient import InfluxClient
from .influxfns import seconds_to_duration_literal
from .influxtypes import BucketGet, DBRPGet, DBRPPost


class BucketMapper(InfluxClient):
    """This is the class that does the work of querying InfluxDB v2 for its
    buckets, determining if buckets lack corresponding DBRPs, and creating
    those if needed.
    """

    async def list_buckets(self) -> List[BucketGet]:
        """List all buckets."""
        itemtype = "buckets"
        url = f"{self.api_url}/{itemtype}"
        b_list = await self.list_all(url, itemtype)
        buckets = [BucketGet(**x) for x in b_list]
        self.log.debug(f"Buckets -> {buckets}")
        return buckets

    async def list_dbrps(self) -> List[DBRPGet]:
        """List all DRBPs."""
        # This method does not appear to be paginated
        # https://docs.influxdata.com/influxdb/v2.2/api/#tag/DBRPs
        d_list: List[Dict[str, Any]] = []
        url = f"{self.api_url}/dbrps"
        obj = await self.get(url)
        d_list = obj["content"]
        dbrps = [DBRPGet(**x) for x in d_list]
        self.log.debug(f"DBRPS -> {dbrps}")
        return dbrps

    async def prepare_buckets_without_dbrps(self) -> List[BucketGet]:
        """Generate a list of buckets whose corresponding DBRPs are missing"""
        buckets = await self.list_buckets()
        dbrps_ids = [x.bucketID for x in await self.list_dbrps()]
        missing_buckets = [x for x in buckets if x.id not in dbrps_ids]
        self.log.info(f"Buckets without DBRPS -> {missing_buckets}")
        return missing_buckets

    def make_dbrp_from_bucket(self, bucket: BucketGet) -> DBRPPost:
        """Given a bucket, construct a DBRP object for it."""

        def get_retention_policy(bucket: BucketGet) -> str:
            """Construct a retention policy name from an expiration policy
            on a bucket.
            """
            rr = bucket.retentionRules
            for r in rr:
                # It's a list...I guess we use the first expire we find?
                # Is it guaranteed to only have one?
                if r["type"] != "expire":
                    continue
                break
            assert type(r["everySeconds"]) is int, "everySeconds is not an int"
            return seconds_to_duration_literal(r["everySeconds"])

        return DBRPPost(
            bucketID=bucket.id,
            database=bucket.name,
            default=True,
            org=self.org,
            retention_policy=get_retention_policy(bucket),
        )

    async def prepare_new_dbrps(self) -> List[DBRPPost]:
        """Generate a list of DBRPs to create"""
        # fmt: off
        new_dbrps = [
            self.make_dbrp_from_bucket(x)
            for x in await self.prepare_buckets_without_dbrps()
        ]
        # fmt: on
        self.log.debug(f"New DBRPS to create -> {new_dbrps}")
        return new_dbrps

    async def create_new_dbrps(self) -> None:
        """Create DBRPs in InfluxDB v2"""
        dbrps = await self.prepare_new_dbrps()
        url = self.api_url + "/dbrps"
        payloads = [asdict(x) for x in dbrps]
        await self.post(url, payloads)

    async def main(self) -> None:
        await self.create_new_dbrps()
