"""
Hyper3D (Rodin Gen-2.5) 3D Model Generation Provider.

Docs: https://docs.hyper3d.ai/zh
Base URL: https://api.hyper3d.com/api/v2
"""

import os
import json
import mimetypes
from pathlib import Path
from typing import List, Optional, Union, Dict, Any, Tuple
import requests

from core.models import GenerationTask, TaskStatus, JobStatus, DownloadItem
from core.exceptions import (
    ProviderError,
    AuthenticationError,
    InsufficientCreditsError,
    RateLimitError,
    InvalidRequestError,
    ContentViolationError,
    TaskFailedError,
)
from core.factory import register_provider
from .base import Base3DModelProvider


DEFAULT_HYPER3D_BASE_URL = "https://api.hyper3d.com/api/v2"


@register_provider("hyper3d")
@register_provider("rodin")
class Hyper3DProvider(Base3DModelProvider):
    """
    Hyper3D / Rodin API Provider for Image-to-3D and Text-to-3D generation.
    """

    provider_name: str = "hyper3d"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = DEFAULT_HYPER3D_BASE_URL,
        timeout: int = 60,
        **kwargs,
    ):
        super().__init__(api_key=api_key, **kwargs)
        self.base_url = base_url.rstrip("/")
        self.request_timeout = timeout
        self.session = requests.Session()

    def _get_headers(self, is_json: bool = True) -> Dict[str, str]:
        self.require_api_key()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "model-creator/1.0",
        }
        if is_json:
            headers["Content-Type"] = "application/json"
        return headers

    def _handle_api_error(self, res_data: dict, status_code: int = None):
        """Map Hyper3D error codes to dedicated exceptions."""
        error_code = res_data.get("error")
        message = res_data.get("message") or f"Hyper3D API error: {error_code or 'Unknown'}"

        if not error_code and (status_code is None or status_code < 400):
            return

        if error_code in (
            "API_NO_ACTIVE_SUBSCRIPTION",
            "API_SUBSCRIPTION_PLAN_TOO_LOW",
            "API_INSUFFICIENT_FUNDS",
        ):
            raise InsufficientCreditsError(
                message,
                provider=self.provider_name,
                status_code=status_code,
                error_code=error_code,
                details=res_data,
            )

        if error_code == "API_PARALLELISM_LIMIT_REACHED" or status_code == 429:
            raise RateLimitError(
                message,
                provider=self.provider_name,
                status_code=status_code,
                error_code=error_code,
                details=res_data,
            )

        if error_code == "PERMISSION_DENIED" or status_code == 401:
            raise AuthenticationError(
                message,
                provider=self.provider_name,
                status_code=status_code,
                error_code=error_code,
                details=res_data,
            )

        if error_code == "IMAGE_CONTENT_VIOLATION":
            raise ContentViolationError(
                message,
                provider=self.provider_name,
                status_code=status_code,
                error_code=error_code,
                details=res_data,
            )

        if error_code in (
            "INVALID_REQUEST",
            "IMAGE_LABEL_LENGTH_TOO_LONG",
            "API_OBJECT_NOT_FOUND_ON_IMAGE",
        ) or status_code == 400:
            raise InvalidRequestError(
                message,
                provider=self.provider_name,
                status_code=status_code,
                error_code=error_code,
                details=res_data,
            )

        raise ProviderError(
            message,
            provider=self.provider_name,
            status_code=status_code,
            error_code=error_code,
            details=res_data,
        )

    @staticmethod
    def _normalize_format(fmt: Optional[str]) -> str:
        """
        Normalize geometry file format and handle common typos (e.g. 'udsz' -> 'usdz').
        Allowed formats in Hyper3D API: glb, usdz, fbx, obj, stl.
        """
        if not fmt:
            return "glb"
        f = fmt.strip().lower().lstrip(".")
        if f == "udsz":
            f = "usdz"
        if f not in ("glb", "usdz", "fbx", "obj", "stl"):
            raise InvalidRequestError(
                f"Unsupported geometry format '{fmt}'. Hyper3D supports: glb, usdz, fbx, obj, stl",
                provider="hyper3d",
            )
        return f

    @staticmethod
    def _resolve_mesh_complexity(
        mesh_complexity: Optional[Union[int, str]] = None,
        triangles: Optional[int] = None,
        quality: Optional[str] = "medium",
        quality_override: Optional[int] = None,
        mesh_mode: Optional[str] = None,
    ) -> Tuple[Optional[str], Optional[int], Optional[str]]:
        """
        Resolves (quality, quality_override, mesh_mode) based on target triangle count
        or mesh complexity according to Hyper3D documentation:

        - 'Raw' mesh mode: Triangle face topology.
        - 'Quad' mesh mode: Quad face topology.
        - When a triangle count is requested (e.g. 5000, 10000, ...), mesh_mode defaults to 'Raw'.
        - quality_override: Custom target face count.
          * Range: 500 to 2,000,000 when mesh_mode is 'Raw' (triangles).
          * Range: 500 to 200,000 when mesh_mode is 'Quad'.
        - quality: Preset target face count ('extra-low', 'low', 'medium', 'high').
          * Gen-2.5 Raw: high=1,000,000, medium=500,000, low=60,000, extra-low=20,000.
          * Quad: high=50,000, medium=18,000, low=8,000, extra-low=4,000.
        """
        target_triangles = triangles
        if target_triangles is None and isinstance(mesh_complexity, int):
            target_triangles = mesh_complexity
        elif target_triangles is None and isinstance(mesh_complexity, str) and mesh_complexity.isdigit():
            target_triangles = int(mesh_complexity)

        if isinstance(mesh_complexity, str) and not mesh_complexity.isdigit():
            preset = mesh_complexity.strip().lower()
            if preset in ("extra-low", "low", "medium", "high"):
                quality = preset

        resolved_override = quality_override
        resolved_mesh_mode = mesh_mode

        if target_triangles is not None:
            if not resolved_mesh_mode:
                resolved_mesh_mode = "Raw"

            max_cap = 200000 if resolved_mesh_mode.lower() == "quad" else 2000000
            min_cap = 500
            if target_triangles < min_cap or target_triangles > max_cap:
                raise InvalidRequestError(
                    f"Target mesh complexity ({target_triangles}) is out of bounds for {resolved_mesh_mode} mode. "
                    f"Hyper3D requires between {min_cap} and {max_cap:,} faces/triangles.",
                    provider="hyper3d",
                )
            resolved_override = target_triangles

        return quality, resolved_override, resolved_mesh_mode

    def _prepare_form_data(self, **kwargs) -> List[Tuple[str, str]]:
        """
        Convert kwargs into multipart/form-data tuples suitable for requests.
        Handles booleans ('true'/'false'), lists, numbers, etc.
        """
        data_tuples = []
        for key, value in kwargs.items():
            if value is None:
                continue

            if isinstance(value, bool):
                data_tuples.append((key, "true" if value else "false"))
            elif isinstance(value, (list, tuple)):
                # If it is an array parameter like addons or image_label, repeat the key
                for item in value:
                    if isinstance(item, bool):
                        data_tuples.append((key, "true" if item else "false"))
                    else:
                        data_tuples.append((key, str(item)))
            elif isinstance(value, dict):
                data_tuples.append((key, json.dumps(value)))
            else:
                data_tuples.append((key, str(value)))

        return data_tuples

    def generate_from_text(
        self,
        prompt: str,
        tier: str = "Gen-2.5-Medium",
        geometry_file_format: Optional[str] = None,
        download_type: Optional[str] = None,
        format: Optional[str] = None,
        mesh_mode: Optional[str] = None,
        quality: Optional[str] = "medium",
        quality_override: Optional[int] = None,
        triangles: Optional[int] = None,
        mesh_complexity: Optional[Union[int, str]] = None,
        texture_mode: Optional[str] = None,
        material: Optional[str] = "PBR",
        seed: Optional[int] = None,
        ta_pose: bool = False,
        preview_render: bool = False,
        is_symmetric: Optional[str] = None,
        geometry_instruct_mode: Optional[str] = None,
        **kwargs,
    ) -> GenerationTask:
        """
        Submit a Text-to-3D generation task to Hyper3D Rodin.
        """
        if not prompt or not prompt.strip():
            raise InvalidRequestError("Prompt cannot be empty for Text-to-3D", provider=self.provider_name)

        # Normalize format / download type (e.g. glb, usdz, fbx, obj, stl; handles 'udsz' typo)
        chosen_format = self._normalize_format(download_type or geometry_file_format or format or "glb")

        # Resolve target mesh complexity / triangle count
        resolved_quality, resolved_override, resolved_mesh_mode = self._resolve_mesh_complexity(
            mesh_complexity=mesh_complexity,
            triangles=triangles,
            quality=quality,
            quality_override=quality_override,
            mesh_mode=mesh_mode,
        )

        # Merge standard options into params
        params = {
            "prompt": prompt.strip(),
            "tier": tier,
            "geometry_file_format": chosen_format,
            "mesh_mode": resolved_mesh_mode,
            "quality": resolved_quality,
            "quality_override": resolved_override,
            "texture_mode": texture_mode,
            "material": material,
            "seed": seed,
            "TAPose": ta_pose if ta_pose else None,
            "preview_render": preview_render if preview_render else None,
            "is_symmetric": is_symmetric,
            "geometry_instruct_mode": geometry_instruct_mode,
            **kwargs,
        }

        form_data = self._prepare_form_data(**params)
        headers = self._get_headers(is_json=False)

        url = f"{self.base_url}/rodin"
        resp = self.session.post(url, headers=headers, data=form_data, timeout=self.request_timeout)

        try:
            res_json = resp.json()
        except Exception:
            resp.raise_for_status()
            raise ProviderError(f"Invalid JSON response: {resp.text[:200]}", provider=self.provider_name)

        if resp.status_code >= 400 or res_json.get("error"):
            self._handle_api_error(res_json, status_code=resp.status_code)

        task_uuid = res_json.get("uuid")
        jobs_info = res_json.get("jobs", {})
        sub_key = jobs_info.get("subscription_key")

        if not task_uuid or not sub_key:
            raise ProviderError(
                f"Unexpected API response missing uuid or subscription_key: {res_json}",
                provider=self.provider_name,
            )

        return GenerationTask(
            task_uuid=task_uuid,
            subscription_key=sub_key,
            provider=self.provider_name,
            prompt=res_json.get("prompt") or prompt,
            consumed_credits=res_json.get("consumed"),
            submit_time=res_json.get("submit_time"),
            raw_response=res_json,
        )

    @staticmethod
    def _optimize_image_for_upload(
        img_path: Path,
        max_dimension: int = 2048,
        quality: int = 95,
        enabled: bool = True,
    ) -> Tuple[str, Any, str]:
        """
        Prepares and optionally optimizes an image before uploading to prevent network timeouts.
        If file size is <= 2MB and max dimension <= max_dimension, returns (filename, open_file, mime_type).
        If image exceeds limits, resizes with high-quality LANCZOS and compresses:
        - RGB -> JPEG 95%
        - RGBA / with alpha -> PNG with preserved alpha.
        """
        if not enabled:
            mime_type, _ = mimetypes.guess_type(str(img_path))
            return img_path.name, open(img_path, "rb"), mime_type or "image/png"

        try:
            from PIL import Image
            import io

            file_size = img_path.stat().st_size
            with Image.open(img_path) as im:
                width, height = im.size
                has_alpha = im.mode in ("RGBA", "LA") or (
                    im.mode == "P" and "transparency" in im.info
                )

                if file_size <= 2 * 1024 * 1024 and max(width, height) <= max_dimension:
                    mime_type, _ = mimetypes.guess_type(str(img_path))
                    return img_path.name, open(img_path, "rb"), mime_type or "image/png"

                # Resize if exceeding max_dimension
                if max(width, height) > max_dimension:
                    scale = max_dimension / max(width, height)
                    new_size = (int(width * scale), int(height * scale))
                    im = im.resize(new_size, Image.Resampling.LANCZOS)

                buf = io.BytesIO()
                if has_alpha:
                    im.save(buf, format="PNG", optimize=True)
                    buf.seek(0)
                    return img_path.name, buf, "image/png"
                else:
                    if im.mode != "RGB":
                        im = im.convert("RGB")
                    im.save(buf, format="JPEG", quality=quality)
                    buf.seek(0)
                    new_name = Path(img_path.name).stem + ".jpg"
                    return new_name, buf, "image/jpeg"
        except Exception:
            mime_type, _ = mimetypes.guess_type(str(img_path))
            return img_path.name, open(img_path, "rb"), mime_type or "image/png"

    def generate_from_image(
        self,
        images: Union[str, Path, List[Union[str, Path]]],
        prompt: Optional[str] = None,
        tier: str = "Gen-2.5-Medium",
        geometry_file_format: Optional[str] = None,
        download_type: Optional[str] = None,
        format: Optional[str] = None,
        mesh_mode: Optional[str] = None,
        quality: Optional[str] = "medium",
        quality_override: Optional[int] = None,
        triangles: Optional[int] = None,
        mesh_complexity: Optional[Union[int, str]] = None,
        texture_mode: Optional[str] = None,
        material: Optional[str] = "PBR",
        seed: Optional[int] = None,
        ta_pose: bool = False,
        preview_render: bool = False,
        is_symmetric: Optional[str] = None,
        geometry_instruct_mode: Optional[str] = None,
        optimize_images: bool = True,
        max_image_dimension: int = 2048,
        upload_timeout: Optional[int] = None,
        **kwargs,
    ) -> GenerationTask:
        """
        Submit an Image-to-3D generation task to Hyper3D Rodin.
        Accepts 1 to 5 images.
        """
        if isinstance(images, (str, Path)):
            img_list = [Path(images)]
        else:
            img_list = [Path(p) for p in images]

        if not img_list:
            raise InvalidRequestError("At least one image is required for Image-to-3D", provider=self.provider_name)
        if len(img_list) > 5:
            raise InvalidRequestError("Hyper3D allows at most 5 images", provider=self.provider_name)

        for p in img_list:
            if not p.is_file():
                raise InvalidRequestError(f"Image file not found: {p}", provider=self.provider_name)

        # Normalize format / download type (e.g. glb, usdz, fbx, obj, stl; handles 'udsz' typo)
        chosen_format = self._normalize_format(download_type or geometry_file_format or format or "glb")

        # Resolve target mesh complexity / triangle count
        resolved_quality, resolved_override, resolved_mesh_mode = self._resolve_mesh_complexity(
            mesh_complexity=mesh_complexity,
            triangles=triangles,
            quality=quality,
            quality_override=quality_override,
            mesh_mode=mesh_mode,
        )

        params = {
            "tier": tier,
            "geometry_file_format": chosen_format,
            "mesh_mode": resolved_mesh_mode,
            "quality": resolved_quality,
            "quality_override": resolved_override,
            "texture_mode": texture_mode,
            "material": material,
            "seed": seed,
            "TAPose": ta_pose if ta_pose else None,
            "preview_render": preview_render if preview_render else None,
            "is_symmetric": is_symmetric,
            "geometry_instruct_mode": geometry_instruct_mode,
            **kwargs,
        }
        if prompt and prompt.strip():
            params["prompt"] = prompt.strip()

        form_data = self._prepare_form_data(**params)
        headers = self._get_headers(is_json=False)

        open_files = []
        files_payload = []
        try:
            for p in img_list:
                fname, f_obj, mime = self._optimize_image_for_upload(
                    p,
                    max_dimension=max_image_dimension,
                    enabled=optimize_images,
                )
                open_files.append(f_obj)
                files_payload.append(("images", (fname, f_obj, mime)))

            effective_timeout = upload_timeout or max(self.request_timeout, 300)
            url = f"{self.base_url}/rodin"
            resp = self.session.post(
                url,
                headers=headers,
                data=form_data,
                files=files_payload,
                timeout=effective_timeout,
            )

            try:
                res_json = resp.json()
            except Exception:
                resp.raise_for_status()
                raise ProviderError(f"Invalid JSON response: {resp.text[:200]}", provider=self.provider_name)

            if resp.status_code >= 400 or res_json.get("error"):
                self._handle_api_error(res_json, status_code=resp.status_code)

            task_uuid = res_json.get("uuid")
            jobs_info = res_json.get("jobs", {})
            sub_key = jobs_info.get("subscription_key")

            if not task_uuid or not sub_key:
                raise ProviderError(
                    f"Unexpected API response missing uuid or subscription_key: {res_json}",
                    provider=self.provider_name,
                )

            return GenerationTask(
                task_uuid=task_uuid,
                subscription_key=sub_key,
                provider=self.provider_name,
                prompt=res_json.get("prompt") or prompt,
                consumed_credits=res_json.get("consumed"),
                submit_time=res_json.get("submit_time"),
                raw_response=res_json,
            )
        finally:
            for f in open_files:
                try:
                    f.close()
                except Exception:
                    pass

    def get_task_status(self, task_or_key: Union[GenerationTask, str]) -> TaskStatus:
        """
        Query generation status using subscription_key.
        """
        if isinstance(task_or_key, GenerationTask):
            subscription_key = task_or_key.subscription_key
        else:
            subscription_key = task_or_key

        if not subscription_key:
            raise InvalidRequestError("subscription_key is required to query status", provider=self.provider_name)

        url = f"{self.base_url}/status"
        headers = self._get_headers(is_json=True)
        payload = {"subscription_key": subscription_key}

        resp = self.session.post(url, headers=headers, json=payload, timeout=self.request_timeout)

        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After")
            wait_sec = float(retry_after) if retry_after else 10.0
            raise RateLimitError(
                "Rate limit exceeded (HTTP 429)",
                provider=self.provider_name,
                status_code=429,
                retry_after=wait_sec,
            )

        try:
            res_json = resp.json()
        except Exception:
            resp.raise_for_status()
            raise ProviderError(f"Invalid JSON response from /status: {resp.text[:200]}", provider=self.provider_name)

        if resp.status_code >= 400 or res_json.get("error"):
            self._handle_api_error(res_json, status_code=resp.status_code)

        jobs_list = []
        for j in res_json.get("jobs", []):
            jobs_list.append(
                JobStatus(
                    uuid=j.get("uuid", ""),
                    status=j.get("status", "Waiting"),
                    queue_length=j.get("queue_length"),
                )
            )

        return TaskStatus(
            jobs=jobs_list,
            error=res_json.get("error"),
            message=res_json.get("message"),
            raw_response=res_json,
        )

    def get_download_list(self, task_or_uuid: Union[GenerationTask, str]) -> List[DownloadItem]:
        """
        Get list of downloadable files for a completed task using task_uuid.
        """
        if isinstance(task_or_uuid, GenerationTask):
            task_uuid = task_or_uuid.task_uuid
        else:
            task_uuid = task_or_uuid

        if not task_uuid:
            raise InvalidRequestError("task_uuid is required to retrieve downloads", provider=self.provider_name)

        url = f"{self.base_url}/download"
        headers = self._get_headers(is_json=True)
        payload = {"task_uuid": task_uuid}

        resp = self.session.post(url, headers=headers, json=payload, timeout=self.request_timeout)

        try:
            res_json = resp.json()
        except Exception:
            resp.raise_for_status()
            raise ProviderError(f"Invalid JSON response from /download: {resp.text[:200]}", provider=self.provider_name)

        if resp.status_code >= 400 or res_json.get("error"):
            self._handle_api_error(res_json, status_code=resp.status_code)

        items = []
        for itm in res_json.get("list", []):
            items.append(DownloadItem(name=itm["name"], url=itm["url"]))
        return items

    def download_results(
        self,
        task_or_uuid: Union[GenerationTask, str],
        output_dir: Union[str, Path],
        file_types: Optional[Union[str, List[str]]] = None,
    ) -> List[Path]:
        """
        Download resulting files into output_dir.
        Optionally filter by file type/extension (e.g. 'glb', 'usdz', 'fbx', 'png').
        """
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        items = self.get_download_list(task_or_uuid)
        downloaded = []

        target_exts = None
        if file_types:
            if isinstance(file_types, str):
                type_list = [t.strip() for t in file_types.split(",") if t.strip()]
            else:
                type_list = [str(t).strip() for t in file_types if str(t).strip()]

            target_exts = set()
            for t in type_list:
                cleaned = t.lower().lstrip(".")
                if cleaned == "udsz":
                    cleaned = "usdz"
                target_exts.add(cleaned)

        for item in items:
            ext = Path(item.name).suffix.lower().lstrip(".")
            if target_exts and ext not in target_exts:
                continue

            target_file = out_path / item.name
            with self.session.get(item.url, stream=True, timeout=self.request_timeout * 2) as r:
                r.raise_for_status()
                with open(target_file, "wb") as f:
                    for chunk in r.iter_content(chunk_size=65536):
                        if chunk:
                            f.write(chunk)
            downloaded.append(target_file)

        return downloaded

    def check_balance(self, usage_page: Optional[int] = None) -> Dict[str, Any]:
        """
        Check current credit balance and optionally usage records.
        """
        url = f"{self.base_url}/check_balance"
        headers = self._get_headers(is_json=True)
        params = {}
        if usage_page is not None:
            params["usage_page"] = usage_page

        resp = self.session.get(url, headers=headers, params=params, timeout=self.request_timeout)

        try:
            res_json = resp.json()
        except Exception:
            resp.raise_for_status()
            raise ProviderError(f"Invalid JSON response from /check_balance: {resp.text[:200]}", provider=self.provider_name)

        if resp.status_code >= 400 or res_json.get("error"):
            self._handle_api_error(res_json, status_code=resp.status_code)

        return res_json
