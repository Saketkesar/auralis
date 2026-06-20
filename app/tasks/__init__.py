"""Celery task wrappers package.

One task wrapper per pipeline stage. Each wrapper runs an engine under the
common contract, catches exceptions, and persists the resulting StageRun and
Finding so a single stage failure never aborts the pipeline.
"""
