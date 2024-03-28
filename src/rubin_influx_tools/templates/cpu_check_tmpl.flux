option v = {bucket: "monitoring", timeRangeStart: -1h, timeRangeStop: now(), windowPeriod: 10000ms}

option task = {name: "{{taskname}}", every: {{every}}, offset: {{offset}} }

cpu_threshold = 90  // Percentage of limit

from(bucket: "{{app_bucket}}")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "kubernetes_pod_container")
  |> filter(fn: (r) => r["_field"] == "cpu_usage_nanocores" or r["_field"] == "resource_limits_millicpu_units" )
  |> drop(columns: ["_start", "_stop", "host", "node_name", "namespace"])
  |> map(fn: (r) => ({r with application_name: "{{app_bucket}}"}))
  |> group()
  |> group(columns: ["pod_name", "container_name", "cluster", "_measurement", "application_name", "_field"])
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> filter(fn: (r) => exists r.resource_limits_millicpu_units and exists r.cpu_usage_nanocores)
  |> map(fn: (r) => ({r with fb: float(v: r.cpu_usage_nanocores) }))
  |> map(fn: (r) => ({r with fl: float(v: r.resource_limits_millicpu_units) * 1000000.0 })) // Convert to nanocores
  |> map(fn: (r) => ({r with _value: float(v: 100.0 * (float(v: r.fb)/float(v: r.fl)))}))
  |> filter(fn: (r) => r._value > cpu_threshold)
  |> map(fn: (r) => ({r with _field: "cpu_pct"}))
  |> map(fn: (r) => ({r with message: "${r.cluster}/${r.application_name}/${r.pod_name} (${r.container_name}) at ${r._time}: ${r._value}% of CPU used"}))
  |> group(columns: ["pod_name", "container_name", "cluster", "application_name", "fb", "fl", "message", "_measurement", "_field"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
  |> yield(name: "mean")
  |> to(bucket: "multiapp_", org: "square")
