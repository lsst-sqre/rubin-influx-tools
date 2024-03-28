option v = {bucket: "monitoring", timeRangeStart: -1h, timeRangeStop: now(), windowPeriod: 10000ms}

option task = {name: "{{taskname}}", every: {{every}}, offset: {{offset}} }

from(bucket: "{{app_bucket}}")
  |> range(start: -15m)
  |> filter(fn: (r) => r["_measurement"] == "kubernetes_pod_container")
  |> filter(fn: (r) => (r["_field"] == "memory_usage_bytes" or r["_field"] == "resource_limits_memory_bytes"))
  |> group(columns: ["_measurement", "_field", "container_name", "pod_name", "cluster"])
  |> aggregateWindow(every: 30s, fn: mean, createEmpty: false)
  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> map(fn: (r) => ({
             _time: r._time,
             _measurement: r._measurement,
             _field: "mem_pct",
             _value: float(v: 100.0 * ((float(v: r.memory_usage_bytes)) / (float(v: r.resource_limits_memory_bytes)))),
             cluster: r.cluster,
             container_name: r.container_name,
             application: "{{app_bucket}}",
             pod_name: r.pod_name,
             resource_limits_memory_bytes: r.resource_limits_memory_bytes,
             memory_usage_bytes: r.memory_usage_bytes,
             message: "${r.cluster}/${r.container_name}/${r.pod_name} at ${r._time}: ${r._value}% of memory used"
             })
             )
  |> filter(fn: (r) => exists r._value)
  |> yield(name: "mean")
  |> to(bucket: "multiapp_", org: "square")
