# rubin-influx-tools

## Bucket and task nomenclature

Our `monitoring` InfluxDBv2 instance assumes that any bucket whose name
neither starts with nor ends with an underscore represents a Kubernetes
application bucket.  Bucket names ending with an underscore are for
measurements that do not pertain to a single Kubernetes application;
some, like `multiapp_`, are used to collect measurements across multiple
applications, while others like `roundtable_internal_` measure
host-level resource usage from Roundtable itself rather than the
satellite RSP instances being monitored.

## Bucketmapper

### Motivation

If you have an InfluxDBv2 installation, but you want to use Chronograf
with it, you will need to create database retention policy mappings
(DBRPs) for each of those buckets; see:

https://docs.influxdata.com/influxdb/v2.2/query-data/influxql/#map-unmapped-buckets

This is irritating and, if you have many buckets, both time-consuming
and error-prone to do by hand.

### Implementation

[bucketmapper](./src/rubin_influx_tools/bucketmapper.py) is a Python 3
class whose `main()` function queries the buckets in an organization,
and creates any mappings that don't yet exist.

The generated database will have the same name as the bucket.

It determines the bucket retention period and creates an appropriate
representation of that period in Influx Duration Literal syntax:

## Tokenmaker

### Motivation

The InfluxDB v2 API only lets you create admin or bucket read/write
tokens.  We would prefer not to run the Task Mapper as full admin, so
therefore we need to create a token with the appropriate scopes.

### Implementation

[tokenmaker](./src/rubin_influx_tools/tokenmaker.py) is a Python 3 class
whose `main()` method, when supplied with an *admin* `INFLUXDB_TOKEN`
will create a new token with sufficient permissions to create tasks for
new application buckets it finds, but not full admin rights.  This only
has to be run once per InfluxDB v2 installation, but does need to
precede running `taskmaker`, since the generated token is the one
`taskmaker` should use.

## Taskmaker

### Motivation

As with BucketMapper: when we find new applications, we want to create
tasks to chart their K8s restarts and alert us when applications
unexpectedly restart.  That's a lot of tasks and it's time-consuming and
error-prone to do manually.

### Implementation

[taskmaker](./src/rubin_influx_tools/taskmaker.py) is a Python 3 class
whose `main()` function queries the buckets in an organization to find
K8s applications, and then determines whether there's a bucket to collect
cross-application results and creates it if necessary.  Then it checks
to see whether each application bucket is matched to a task to watch
that application for pod restarts and pod-not-running states creates any
tasks it needs to.  Finally, it creates tasks to periodically check the
cross-application bucket (called `multiapp_`) for entries indicating
that it needs to send an alert to Slack, as well as a check for
Roundtable node disk space (also alerted to Slack).

The Slack webhook URL is stored within InfluxDB2 as a (manually-created)
secret.

## Configuration

These tools expect the same environment variables as InfluxDBv2 or Chronograf:

- `INFLUXDB_TOKEN`
- `INFLUXDB_ORG`
- `INFLUXDB_URL`

Use the organization _name_ rather than its ID here.

The only third-party Python libraries required for runtime operation are
[aiohttp](https://docs.aiohttp.org/en/stable/) and
[jinja](https://jinja.palletsprojects.com/en/3.1.x/).  They are captured
in [requirements.in](requirements/requirements.in).  A frozen
requirements file is generated with `make update-deps`.

### Development

You will need Python 3.9 or later, GNU Make, and git.  You will want a
virtualenv into which you have installed `pre-commit` with `pip install
pre-commit`.  Then `make update-deps` followed by `make init` will set
up everything you need to develop the Rubin Observatory Influx Tools.

## Docker container

We also supply a [Dockerfile](./Dockerfile), which builds a container
suitable for running as a Kubernetes CronJob (when supplied with the
appropriate environment variables).  The container can also be found in
[Packages](./pkgs/container/influx-restart-mapper).  This container is
built upon release by Github Actions CI.

## License

The Rubin Observatory Influx Tools are licensed under the
[MIT License](./LICENSE).
