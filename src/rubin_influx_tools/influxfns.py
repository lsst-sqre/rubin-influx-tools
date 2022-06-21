from datetime import timedelta
from os.path import dirname, join

from jinja2 import Template


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


def get_template(
    name: str,
    prefix: str = "",
    template_marker: str = "_tmpl.flux",
    dir: str = join(dirname(__file__), "templates"),
) -> Template:
    """Convenience function for retrieving a Jinja2 Template from a static
    templated query.
    """
    fn = join(dir, prefix + name + template_marker)
    with open(fn) as f:
        txt = f.read()
    return Template(txt)  # the shared default environment is fine
