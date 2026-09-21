"""
Data models and representations for 3D model generation tasks and results.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any


@dataclass
class GenerationTask:
    """Represents a submitted 3D model generation task."""
    task_uuid: str
    subscription_key: Optional[str] = None
    provider: str = "hyper3d"
    prompt: Optional[str] = None
    consumed_credits: Optional[float] = None
    submit_time: Optional[str] = None
    raw_response: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_uuid": self.task_uuid,
            "subscription_key": self.subscription_key,
            "provider": self.provider,
            "prompt": self.prompt,
            "consumed_credits": self.consumed_credits,
            "submit_time": self.submit_time,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class JobStatus:
    """Status of an individual sub-job within a generation task."""
    uuid: str
    status: str  # "Waiting", "Generating", "Done", "Failed"
    queue_length: Optional[int] = None

    @property
    def is_done(self) -> bool:
        return self.status.lower() == "done"

    @property
    def is_failed(self) -> bool:
        return self.status.lower() == "failed"

    @property
    def is_generating(self) -> bool:
        return self.status.lower() == "generating"

    @property
    def is_waiting(self) -> bool:
        return self.status.lower() == "waiting"


@dataclass
class TaskStatus:
    """Overall status of a generation task across all its sub-jobs."""
    jobs: List[JobStatus] = field(default_factory=list)
    error: Optional[str] = None
    message: Optional[str] = None
    raw_response: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_done(self) -> bool:
        """True only if there is at least one job and ALL jobs are Done."""
        return bool(self.jobs) and all(job.is_done for job in self.jobs)

    @property
    def is_failed(self) -> bool:
        """True if any job is Failed or an error was returned."""
        return bool(self.error) or any(job.is_failed for job in self.jobs)

    @property
    def is_pending(self) -> bool:
        """True if task is still queued or actively generating."""
        return not self.is_done and not self.is_failed

    @property
    def summary(self) -> str:
        if self.is_failed:
            err = self.error or self.message or "Unknown failure"
            return f"Failed: {err}"
        if self.is_done:
            return "Done"

        # Check generating / waiting details
        generating_count = sum(1 for j in self.jobs if j.is_generating)
        waiting_count = sum(1 for j in self.jobs if j.is_waiting)
        queue_info = [f"queue={j.queue_length}" for j in self.jobs if j.queue_length is not None]
        q_str = f" ({', '.join(queue_info)})" if queue_info else ""

        if generating_count > 0:
            return f"Generating ({generating_count}/{len(self.jobs)} active){q_str}"
        elif waiting_count > 0:
            return f"Waiting in queue{q_str}"
        return "Processing"


@dataclass
class DownloadItem:
    """Information about an available download file for a task."""
    name: str
    url: str


@dataclass
class GenerationResult:
    """Complete outcome of a generated and downloaded 3D model."""
    task: GenerationTask
    output_dir: Path
    downloaded_files: List[Path] = field(default_factory=list)
    duration_seconds: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def primary_model_file(self) -> Optional[Path]:
        """Convenience property to locate the primary 3D mesh file."""
        mesh_extensions = {".glb", ".usdz", ".fbx", ".obj", ".stl"}
        for f in self.downloaded_files:
            if f.suffix.lower() in mesh_extensions:
                return f
        return None

    @property
    def preview_file(self) -> Optional[Path]:
        """Convenience property to locate an exported preview render."""
        img_extensions = {".png", ".jpg", ".jpeg", ".webp"}
        for f in self.downloaded_files:
            if f.suffix.lower() in img_extensions:
                return f
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task": self.task.to_dict(),
            "output_dir": str(self.output_dir),
            "primary_model_file": str(self.primary_model_file) if self.primary_model_file else None,
            "preview_file": str(self.preview_file) if self.preview_file else None,
            "downloaded_files": [str(p) for p in self.downloaded_files],
            "duration_seconds": round(self.duration_seconds, 2),
            "metadata": self.metadata,
        }
