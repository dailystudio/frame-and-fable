"""
Base abstract class for 3D model generation providers.
"""

from abc import ABC, abstractmethod
from pathlib import Path
import time
from typing import List, Optional, Union, Dict, Any, Callable

from core.models import GenerationTask, TaskStatus, GenerationResult
from core.exceptions import (
    AuthenticationError,
    TaskTimeoutError,
    TaskFailedError,
    RateLimitError,
)
from core.config import (
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_POLL_INTERVAL_MIN,
    DEFAULT_POLL_INTERVAL_MAX,
)


class Base3DModelProvider(ABC):
    """
    Abstract interface for 3D generation providers (Hyper3D, Tripo3D, Meshy, etc.).
    """

    provider_name: str = "base"

    def __init__(self, api_key: Optional[str] = None, **kwargs):
        self.api_key = api_key
        self.extra_config = kwargs

    def require_api_key(self):
        """Ensure an API key is configured."""
        if not self.api_key or not self.api_key.strip():
            raise AuthenticationError(
                f"API Key for provider '{self.provider_name}' is missing. "
                f"Pass it via api_key or set the corresponding environment variable (e.g. HYPER3D_API_KEY).",
                provider=self.provider_name,
            )

    @abstractmethod
    def generate_from_text(self, prompt: str, **kwargs) -> GenerationTask:
        """
        Submit a Text-to-3D generation task.
        """
        pass

    @abstractmethod
    def generate_from_image(
        self,
        images: Union[str, Path, List[Union[str, Path]]],
        prompt: Optional[str] = None,
        **kwargs,
    ) -> GenerationTask:
        """
        Submit an Image-to-3D generation task.
        """
        pass

    @abstractmethod
    def get_task_status(self, task_or_key: Union[GenerationTask, str]) -> TaskStatus:
        """
        Query current status of a generation task.
        """
        pass

    @abstractmethod
    def download_results(
        self,
        task_or_uuid: Union[GenerationTask, str],
        output_dir: Union[str, Path],
        file_types: Optional[Union[str, List[str]]] = None,
    ) -> List[Path]:
        """
        Download resulting files of a completed task into output_dir.
        Optionally filter by file type/extension (e.g. 'glb', 'usdz', 'fbx').
        """
        pass

    @abstractmethod
    def check_balance(self) -> Dict[str, Any]:
        """
        Check account credits/balance.
        """
        pass

    def poll_until_complete(
        self,
        task: GenerationTask,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        initial_delay: float = DEFAULT_POLL_INTERVAL_MIN,
        max_delay: float = DEFAULT_POLL_INTERVAL_MAX,
        status_callback: Optional[Callable[[TaskStatus, float], None]] = None,
    ) -> TaskStatus:
        """
        Poll task status with progressive exponential backoff until completion or failure.
        """
        started_at = time.monotonic()
        delay = initial_delay

        # Initial wait before first status request as recommended by providers
        time.sleep(delay)

        while True:
            elapsed = time.monotonic() - started_at
            if elapsed >= timeout:
                raise TaskTimeoutError(
                    f"Generation task {task.task_uuid} did not complete within {timeout}s"
                )

            try:
                status = self.get_task_status(task)
            except RateLimitError as e:
                # Obey Retry-After if provided
                wait_time = e.retry_after or delay
                time.sleep(wait_time)
                continue

            if status_callback:
                status_callback(status, elapsed)

            if status.is_failed:
                raise TaskFailedError(
                    f"Task {task.task_uuid} failed: {status.summary}",
                    provider=self.provider_name,
                    error_code=status.error,
                    details=status.raw_response,
                )

            if status.is_done:
                return status

            # Progressive backoff
            time.sleep(delay)
            delay = min(delay + 5.0, max_delay)

    def create_from_text(
        self,
        prompt: str,
        output_dir: Union[str, Path],
        wait: bool = True,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        status_callback: Optional[Callable[[TaskStatus, float], None]] = None,
        download_types: Optional[Union[str, List[str]]] = None,
        **kwargs,
    ) -> GenerationResult:
        """
        Convenience all-in-one method: submit text prompt, optionally wait for completion,
        and download result files to output_dir.
        """
        start_time = time.monotonic()
        task = self.generate_from_text(prompt=prompt, **kwargs)

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        downloaded_files = []
        if wait:
            self.poll_until_complete(
                task,
                timeout=timeout,
                status_callback=status_callback,
            )
            downloaded_files = self.download_results(task, output_path, file_types=download_types)

        duration = time.monotonic() - start_time
        return GenerationResult(
            task=task,
            output_dir=output_path,
            downloaded_files=downloaded_files,
            duration_seconds=duration,
            metadata={"prompt": prompt, "parameters": kwargs},
        )

    def create_from_image(
        self,
        images: Union[str, Path, List[Union[str, Path]]],
        output_dir: Union[str, Path],
        prompt: Optional[str] = None,
        wait: bool = True,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        status_callback: Optional[Callable[[TaskStatus, float], None]] = None,
        download_types: Optional[Union[str, List[str]]] = None,
        **kwargs,
    ) -> GenerationResult:
        """
        Convenience all-in-one method: submit input image(s), optionally wait for completion,
        and download result files to output_dir.
        """
        start_time = time.monotonic()
        task = self.generate_from_image(images=images, prompt=prompt, **kwargs)

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        downloaded_files = []
        if wait:
            self.poll_until_complete(
                task,
                timeout=timeout,
                status_callback=status_callback,
            )
            downloaded_files = self.download_results(task, output_path, file_types=download_types)

        duration = time.monotonic() - start_time
        return GenerationResult(
            task=task,
            output_dir=output_path,
            downloaded_files=downloaded_files,
            duration_seconds=duration,
            metadata={"prompt": prompt, "parameters": kwargs},
        )
