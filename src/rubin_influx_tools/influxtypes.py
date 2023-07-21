"""Types for Rubin Observatory InfluxDB v2 management."""
from dataclasses import dataclass, field
from typing import Dict, List, Union

# Simple typealiases to represent InfluxDB v2 object fields
# Unless otherwise specified, they can be found at:
#      https://docs.influxdata.com/influxdb/v2.2/api/#operation/GetBuckets
# "self" doesn't work as an object attribute, unsurprisingly.

RetentionRule = Dict[str, Union[int, str]]
"""An InfluxDB v2 RetentionRule.  Valid keys:
* everySeconds: int
* shardGroupDurationSeconds: int
* type: str
"""


BucketLinks = List[Dict[str, str]]
"""Links for a Bucket object.  Valid keys (all str):
* labels
* members
* org
* owners
* self
* write
"""

URILinks = List[Dict[str, str]]
"""Links for a paginated InfluxDB v2 object.  Valid keys:
* self
* next
* prev
"""

# Some dataclasses to represent InfluxDB v2 objects
# Unless otherwise specified, they can be found at:
#      https://docs.influxdata.com/influxdb/v2.2/api/#operation/GetBuckets


@dataclass
class Label:
    """An InfluxDB Label."""

    id: str = ""
    name: str = ""
    orgId: str = ""
    properties: Dict[str, str] = field(default_factory=dict)


@dataclass
class BucketGet:
    """An InfluxDB v2 Bucket, as returned from
    https://docs.influxdata.com/influxdb/v2.2/api/#operation/GetBuckets
    """

    createdAt: str = ""
    description: str = ""
    id: str = ""
    orgID: str = ""
    updatedAt: str = ""
    labels: list[Label] = field(default_factory=list)
    links: list[BucketLinks] = field(default_factory=list)
    name: str = ""
    retentionRules: list[RetentionRule] = field(default_factory=list)
    type: str = "user"


@dataclass
class BucketPost:
    """An InfluxDB v2 Bucket, that you would send to
    https://docs.influxdata.com/influxdb/v2.2/api/#operation/PostBuckets
    """

    description: str = ""
    name: str = ""
    orgID: str = ""
    retentionRules: list[RetentionRule] = field(default_factory=list)


@dataclass
class DBRPGet:
    """An InfluxDB v2 DBRP, as you'd receive it when listing them.
    https://docs.influxdata.com/influxdb/cloud/api/#operation/GetDBRPs
    """

    bucketID: str
    database: str
    default: bool
    id: str
    orgID: str
    retention_policy: str
    links: list[URILinks] = field(default_factory=list)
    virtual: bool = False


@dataclass
class DBRPPost:
    """An InfluxDB v2 DBRP, as you'd send it when creating one:
    https://docs.influxdata.com/influxdb/cloud/api/#operation/PosttDBRPs

    We assume you're going to use the org name rather than the orgID.
    """

    bucketID: str
    database: str
    org: str
    retention_policy: str
    default: bool = False


@dataclass
class TaskGet:
    """An InfluxDB v2 Task, as returned from
    https://docs.influxdata.com/influxdb/v2.2/api/#operation/GetTasks
    """

    authorizationID: str = ""
    createdAt: str = ""
    cron: str = ""
    description: str = ""
    every: str = ""
    flux: str = ""
    id: str = ""
    orgID: str = ""
    labels: List[Label] = field(default_factory=list)
    lastRunError: str = ""
    lastRunStatus: str = ""
    latestCompleted: str = ""
    links: list[BucketLinks] = field(default_factory=list)
    name: str = ""
    offset: str = ""
    org: str = ""
    ownerID: str = ""
    status: str = ""
    type: str = ""
    updatedAt: str = ""


@dataclass
class TaskPost:
    """An InfluxDB v2 Task definition you'd send to create the Task."""

    description: str = ""
    flux: str = ""
    org: str = ""
    orgID: str = ""
    status: str = "active"


@dataclass
class Resource:
    """Resource for permissions to apply to."""

    type: str = ""


@dataclass
class Permission:
    """A Permission for an InfluxDB v2 auth."""

    action: str = ""  # "read" or "write"
    resource: Resource = field(default_factory=Resource)


@dataclass
class TokenPost:
    """An InfluxDB v2 Token definition you'd send to create an auth token."""

    description: str = ""
    orgID: str = ""
    permissions: List[Permission] = field(default_factory=list)
    status: str = "active"


@dataclass
class DashboardQuery:
    """The dashboard query associated with a check."""

    editMode: str = "advanced"
    name: str = ""
    text: str = ""


@dataclass
class CheckPost:
    """An InfluxDB v2 Check definition you'd send to create a check."""

    # We are leaving out Threshold, since it's complex and we will just
    # create the threshold criteria in the flux check itself.
    # Likewise, we're leaving out the task ID, since we're just supplying the
    # flux code to build the associated task.
    description: str = ""
    every: str = ""
    labels: List[Label] = field(default_factory=list)
    offset: str = ""
    orgID: str = ""
    query: DashboardQuery = field(default_factory=DashboardQuery)
    status: str = "active"
    type: str = "custom"
