# rubin-influx-tools

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
precede running `restartmapper`, since the generated token is the one
`restartmapper` should use.

## Restartmapper

### Motivation

As with BucketMapper: when we find new applications, we want to create
tasks to chart their K8s restarts and alert us when applications
unexpectedly restart.  That's a lot of tasks and it's time-consuming and
error-prone to do manually.

### Implementation

[restartmapper](./src/rubin_influx_tools/restartmapper.py) is a Python 3 class
whose `main()` function queries the buckets in an organization to find
K8s applications, checks to see whether each bucket is matched to a task
to watch that application for pod restarts, and creates any tasks it
finds missing.

Currently creation of the subsequent check and alert notification rules
is manual.

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


