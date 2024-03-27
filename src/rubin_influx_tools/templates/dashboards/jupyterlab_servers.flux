from(bucket: "nublado")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["cluster"] == v.cluster)
  |> filter(fn: (r) => r["_measurement"] == "prometheus_hub")
  |> filter(fn: (r) => r["_field"] == "jupyterhub_running_servers")
  |> drop(columns: ["_measurement", "_field", "_start", "_stop", "url", "prometheus_app"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
  |> yield(name: "mean")
