option v = {bucket: "_monitoring", timeRangeStart: -1h, timeRangeStop: now(), windowPeriod: 10000ms}

option task = {name: "{{taskname}}", every: {{every}}, offset: {{offset}} }

from(bucket: "{{app_bucket}}")
    |> range(start: -5m)
    |> filter(fn: (r) => r["_measurement"] == "kubernetes_pod_container")
    |> filter(fn: (r) => r["_field"] == "restarts_total")
    |> group(columns: ["_measurement", "_field", "container_name", "pod_name", "cluster"])
    |> drop(columns: ["_start",
                      "_stop",
                      "host",
                      "namespace"])
    |> aggregateWindow(every: 10s, fn: max, createEmpty: false)
    |> difference(columns: ["_value"])
    |> filter(fn: (r) => r._value != 0)
    |> map(fn: (r) => ({
            _time: r._time,
            _measurement: r._measurement,
            _field: "differential_restarts",
            _value: int(v: r._value),
            cluster: r.cluster,
            container_name: r.container_name,
            application: "{{app_bucket}}",
            message: "Restart(s) for ${r.cluster}/${r.application}/${r.pod_name} (${r.container_name}) at ${r._time}: ${r._value}",
            phase: r.phase,
            pod_name: r.pod_name,
            readiness: r.readiness,
            state: r.state
          })
        )
    |> to(bucket: "multiapp_", org: "square")
