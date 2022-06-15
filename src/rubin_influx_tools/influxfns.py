from datetime import timedelta


def seconds_to_duration_literal(seconds: int) -> str:
    """You'd really think this would be a library function already.

    Weirdly, although InfluxDB v2 lets you specify this down to
    nanoseconds, the object you get back from the API call only has
    second precision.
    """
    if seconds == 0:
        return "infinite"
    dls = ""
    duration = timedelta(seconds=seconds)
    if duration.days:
        weeks = duration.days // 7
        days = duration.days - weeks * 7
        if weeks:
            dls += f"{weeks}w"
        if days:
            dls += f"{days}d"
    if duration.seconds:
        hours = duration.seconds // (60 * 60)
        minutes = (duration.seconds - hours * 60 * 60) // 60
        secs = (duration.seconds - hours * 60 * 60) - minutes * 60
        if hours:
            dls += f"{hours}h"
        if minutes:
            dls += f"{minutes}m"
        if secs:
            dls += f"{secs}s"
    return dls
