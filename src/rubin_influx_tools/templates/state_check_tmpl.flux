option v = {bucket: "_monitoring", timeRangeStart: -1h, timeRangeStop: now(), windowPeriod: 10000ms}

option task = {name: "{{taskname}}", every: {{every}}, offset: {{offset}} }

from(bucket: "{{app_bucket}}")
  |> range(start: -15m)
  |> filter(fn: (r) => r["_measurement"] == "kubernetes_pod_container")
  |> filter(fn: (r) => (r["_field"] == "state_code"))
  |> filter(fn: (r) => (r["_value"] != 0))
  |> group(columns: ["_measurement", "_field", "container_name", "pod_name", "cluster"])
  |> aggregateWindow(every: 30s, fn: mean, createEmpty: false)
  |> map(fn: (r) => ({
             _time: r._time,
             _measurement: r._measurement,
             _field: "state_code",
             _value: r._value,
             cluster: r.cluster,
             container_name: r.container_name,
             application: "{{app_bucket}}",
             pod_name: r.pod_name,
             phase: r.phase,
             state: r.state,
             readiness: r.readiness,
             state_reason: r.state_reason,
             phase_reason: r.phase_reason
             })
             )
  |> yield(name: "mean")
  |> to(bucket: "multiapp_", org: "square")
