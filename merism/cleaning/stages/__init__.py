"""Cleaning stages. Each stage is a plain async function:

    async def stage(turns: list[dict], context: StageContext) -> list[dict]:
        ...

The pipeline in :mod:`merism.cleaning.pipeline` runs them in order,
passing the output of each stage as input to the next.
"""
