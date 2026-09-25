from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import sys
from pathlib import Path

from app.contracts import (
    Material,
    MaterialCategory,
    MaterialParseStatus,
    MaterialQualityStatus,
)
from app.providers import (
    CompatibleOcrProvider,
    MaterialInput,
    ProviderError,
)
from app.settings import (
    ProviderConfigurationError,
    VlmSettings,
)

SUPPORTED_MEDIA_TYPES = {
    "image/jpeg",
    "image/png",
}


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="使用真实多模态模型识别一张光伏投保材料图片。",
    )
    parser.add_argument(
        "image",
        type=Path,
        help="待识别的 JPEG 或 PNG 图片路径。",
    )
    parser.add_argument(
        "--category",
        choices=[
            category.value
            for category in MaterialCategory
        ],
        default=(
            MaterialCategory
            .COMPONENT_NAMEPLATE
            .value
        ),
        help="材料类别，默认为 component_nameplate。",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "outputs/real_ocr_result.json"
        ),
        help="OCR 结果 JSON 的保存路径。",
    )
    return parser.parse_args()


def detect_media_type(
    image_path: Path,
) -> str:
    media_type, _ = mimetypes.guess_type(
        image_path.name
    )

    if media_type == "image/jpg":
        media_type = "image/jpeg"

    if media_type not in SUPPORTED_MEDIA_TYPES:
        supported = ", ".join(
            sorted(SUPPORTED_MEDIA_TYPES)
        )
        raise ValueError(
            "不支持的图片格式："
            f"{media_type or 'unknown'}；"
            f"当前支持：{supported}"
        )

    return media_type


def main() -> int:
    arguments = parse_arguments()
    image_path = (
        arguments.image
        .expanduser()
        .resolve()
    )
    output_path = (
        arguments.output
        .expanduser()
        .resolve()
    )

    if not image_path.is_file():
        print(
            f"图片不存在：{image_path}",
            file=sys.stderr,
        )
        return 1

    try:
        content = image_path.read_bytes()

        if not content:
            raise ValueError("图片文件为空")

        media_type = detect_media_type(
            image_path
        )
        settings = (
            VlmSettings.from_environment()
        )

        material = Material(
            material_id="material-real-ocr-001",
            category=MaterialCategory(
                arguments.category
            ),
            file_name=image_path.name,
            media_type=media_type,
            sha256=hashlib.sha256(
                content
            ).hexdigest(),
            captured_at=None,
            longitude=None,
            latitude=None,
            quality_status=(
                MaterialQualityStatus.USABLE
            ),
            quality_confidence=1.0,
            quality_issues=[],
            parse_status=(
                MaterialParseStatus.SUCCESS
            ),
        )

        material_input = MaterialInput(
            material=material,
            content=content,
        )

        provider = CompatibleOcrProvider(
            settings=settings,
        )

        print(f"Model: {provider.model_name}")
        print(f"Image: {image_path}")
        print(f"Media type: {media_type}")
        print(
            f"Category: {material.category.value}"
        )
        print("正在调用 OCR 模型……")

        fields = provider.extract(
            material_input
        )

        result = {
            "model": provider.model_name,
            "material_id": material.material_id,
            "file_name": material.file_name,
            "category": material.category.value,
            "field_count": len(fields),
            "fields": [
                field.model_dump(mode="json")
                for field in fields
            ],
        }

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        output_path.write_text(
            json.dumps(
                result,
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )

    except (
        OSError,
        ProviderConfigurationError,
        ProviderError,
        ValueError,
    ) as exc:
        print(
            f"调用失败：{exc}",
            file=sys.stderr,
        )
        return 1

    print(
        f"识别完成，共提取 {len(fields)} 个字段。"
    )
    print(f"结果已保存：{output_path}")
    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
