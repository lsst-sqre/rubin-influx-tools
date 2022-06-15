#!/usr/bin/env python3
import asyncio
import sys
from os.path import basename
from typing import Dict

from . import BucketMapper, InfluxClient, RestartMapper, TokenMaker

KLASSMAP: Dict[str, type[InfluxClient]] = {
    "bucketmapper": BucketMapper,
    "tokenmaker": TokenMaker,
    "restartmapper": RestartMapper,
}


def main() -> None:
    asyncio.run(async_main())


async def async_main() -> None:
    me = basename(sys.argv[0])
    try:
        klass = KLASSMAP[me]
        async with klass() as obj:
            await obj.main()
    except KeyError:
        errstr = f"'{me}' is not any of {list(KLASSMAP.keys())}"
        raise RuntimeError(errstr)


async def bucketmapper() -> None:
    async with BucketMapper() as bm:
        await bm.main()


async def tokenmaker() -> None:
    async with TokenMaker() as bm:
        await bm.main()


async def restartmapper() -> None:
    async with RestartMapper() as bm:
        await bm.main()


if __name__ == "__main__":
    main()
