// Do nothing.  This will be handled by the state check Slack task.

from(bucket: "multiapp_")
    |> range(start: -1m)
    |> filter(fn: (r) => false)
    |> yield()
