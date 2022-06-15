# This is designed to be run as a K8s CronJob, with the environment variables
# INFLUXDB_TOKEN, INFLUXDB_URL, and INFLUXDB_ORG set.
#
# The scopes required for INFLUXDB_TOKEN vary between the entrypoints, so
# (unless you use a generic admin token, which we do *not* recommend) you
# will need to provide your different CronJobs with different tokens.

FROM library/python:3-alpine
RUN apk add git
RUN mkdir /workdir
WORKDIR /workdir
COPY requirements/main.txt /workdir/requirements.txt
RUN pip install --upgrade --no-cache-dir pip setuptools wheel
RUN pip install --no-cache-dir -r /workdir/requirements.txt
COPY . /workdir
RUN pip install --no-cache-dir .
USER guest
# Change the command (to "restartmapper") if you like.
CMD ["bucketmapper"]
