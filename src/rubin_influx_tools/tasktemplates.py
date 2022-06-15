import jinja2

# This is mostly embedded Flux, and does not follow Python rules.

# flake8: noqa

# Task template; shared Jinja2 env is fine.
task_template = jinja2.Template(
    """option v = {bucket: "_monitoring", timeRangeStart: -1h, timeRangeStop: now(), windowPeriod: 10000ms}

option task = {name: "{{taskname}}", every: 1m}

from(bucket: "{{app_bucket}}")
    |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
    |> filter(fn: (r) => r["_measurement"] == "kubernetes_pod_container")
    |> drop(
        columns: [
            "_start",
            "_stop",
            "_host",
            "namespace",
            "host",
            "node_name",
            "phase",
            "readiness",
            "state",
        ],
    )
    |> filter(fn: (r) => r["_field"] == "restarts_total")
    |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
    |> tail(n: 2)
    |> difference(columns: ["_value"])
    |> yield(name: "mean")
    |> to(bucket: "restarts_", org: "square")
"""
)

check_text = """import "influxdata/influxdb/monitor"
import "influxdata/influxdb/v1"

data =
    from(bucket: "restarts_")
        |> range(start: -1m)
        |> filter(fn: (r) => r["_measurement"] == "kubernetes_pod_container")
        |> filter(fn: (r) => r["_field"] == "restarts_total")
        |> aggregateWindow(every: 1m, fn: last, createEmpty: false)

crit = (r) => r["restarts_total"] != 0.0
messageFn = (r) => "Check: ${r._check_name}: ${r._value} restarts for ${r.cluster}/${r.container_name}/${r.pod_name}"

data |> v1["fieldsAsCols"]() |> monitor["check"](data: check, messageFn: messageFn, crit: crit)
"""
