from __future__ import annotations

import atexit
import re
import shutil
import socket
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

from .color_by_number import ColorByNumber


MIN_IMAGE_DIMENSION = 20
MAX_DEFAULT_BLOCKS = 32
MAX_DEFAULT_COLORS = 10
MAX_CANVAS_SIZE = 896
DEFAULT_LEGEND_COLUMNS = 2
TEMP_DIR_PREFIX = "color_by_number_"

_ACTIVE_TEMP_DIRS: set[Path] = set()


@dataclass(frozen=True)
class GenerationSettings:
    number_of_blocks: int
    number_of_colors: int
    block_size: int
    legend_columns: int = DEFAULT_LEGEND_COLUMNS
    show_numbers: bool = False


@dataclass
class GeneratedArtifacts:
    stem: str
    temp_dir: Path
    uploaded_image_path: Path
    puzzle_image: Image.Image
    legend_image: Image.Image
    completed_image: Image.Image
    puzzle_path: Path
    legend_path: Path
    completed_path: Path
    zip_path: Path

    def cleanup(self) -> None:
        cleanup_temp_dir(self.temp_dir)


def derive_generation_settings(width: int, height: int) -> GenerationSettings:
    if width < MIN_IMAGE_DIMENSION or height < MIN_IMAGE_DIMENSION:
        raise ValueError(
            f"Please upload an image that is at least {MIN_IMAGE_DIMENSION}px on both sides."
        )

    if width >= height:
        number_of_blocks = min(MAX_DEFAULT_BLOCKS, width)
    else:
        number_of_blocks = min(width, max(1, round(MAX_DEFAULT_BLOCKS * width / height)))

    estimated_rows = max(1, round(height / width * number_of_blocks))
    number_of_colors = max(1, min(MAX_DEFAULT_COLORS, number_of_blocks * estimated_rows))
    block_size = max(8, min(28, MAX_CANVAS_SIZE // max(number_of_blocks, estimated_rows)))

    return GenerationSettings(
        number_of_blocks=number_of_blocks,
        number_of_colors=number_of_colors,
        block_size=block_size,
    )


def generate_artifacts(uploaded_image_path: str | Path | None) -> GeneratedArtifacts:
    if uploaded_image_path is None or str(uploaded_image_path).strip() == "":
        raise ValueError("Please upload an image to generate a color-by-number set.")

    source_path = Path(uploaded_image_path)
    if not source_path.exists():
        raise ValueError("The uploaded image could not be found. Please upload it again.")

    stem = _sanitize_stem(source_path.stem)
    temp_dir = Path(tempfile.mkdtemp(prefix=TEMP_DIR_PREFIX))
    _register_temp_dir(temp_dir)

    try:
        with Image.open(source_path) as image:
            normalized_image = ImageOps.exif_transpose(image).convert("RGB")
            width, height = normalized_image.size
            settings = derive_generation_settings(width, height)

            uploaded_copy_path = temp_dir / f"{stem}_input.png"
            normalized_image.save(uploaded_copy_path)

        generator = ColorByNumber(
            fig_path=str(uploaded_copy_path),
            number_of_colors=settings.number_of_colors,
            number_of_blocks=settings.number_of_blocks,
        )

        puzzle_image = generator.generate_mosaic(block_size=settings.block_size)
        legend_image = generator.generate_reference_color_bar(
            columns=settings.legend_columns
        )
        completed_image = generator.complete_mosaic(
            block_size=settings.block_size,
            show_numbers=settings.show_numbers,
        )

        puzzle_path = temp_dir / f"{stem}_puzzle.png"
        legend_path = temp_dir / f"{stem}_legend.png"
        completed_path = temp_dir / f"{stem}_completed.png"
        zip_path = temp_dir / f"{stem}_color_by_number_bundle.zip"

        puzzle_image.save(puzzle_path)
        legend_image.save(legend_path)
        completed_image.save(completed_path)
        _create_zip_bundle(zip_path, puzzle_path, legend_path, completed_path)

        return GeneratedArtifacts(
            stem=stem,
            temp_dir=temp_dir,
            uploaded_image_path=uploaded_copy_path,
            puzzle_image=puzzle_image,
            legend_image=legend_image,
            completed_image=completed_image,
            puzzle_path=puzzle_path,
            legend_path=legend_path,
            completed_path=completed_path,
            zip_path=zip_path,
        )
    except Exception:
        cleanup_temp_dir(temp_dir)
        raise


def cleanup_temp_dir(temp_dir: str | Path | None) -> None:
    if temp_dir is None or str(temp_dir).strip() == "":
        return

    path = Path(temp_dir)
    if path not in _ACTIVE_TEMP_DIRS:
        return

    shutil.rmtree(path, ignore_errors=True)
    _ACTIVE_TEMP_DIRS.discard(path)


def build_app() -> Any:
    gr = _import_gradio()

    def on_generate(
        uploaded_image_path: str | None,
        current_temp_dir: str | None,
    ) -> tuple[Image.Image, Image.Image, Image.Image, str, str]:
        try:
            artifacts = generate_artifacts(uploaded_image_path)
        except ValueError as exc:
            raise gr.Error(str(exc)) from exc

        cleanup_temp_dir(current_temp_dir)

        return (
            artifacts.completed_image,
            artifacts.puzzle_image,
            artifacts.legend_image,
            str(artifacts.zip_path),
            str(artifacts.temp_dir),
        )

    def on_clear(current_temp_dir: str | None) -> tuple[None, None, None, None, None, None]:
        cleanup_temp_dir(current_temp_dir)
        return None, None, None, None, None, None

    with gr.Blocks(title="Color By Number Generator") as demo:
        gr.Markdown(
            """
            # Color By Number Generator
            Upload an image to generate a completed preview, a numbered puzzle,
            a color legend, and a ZIP file with all three outputs.
            """
        )

        temp_dir_state = gr.State(value=None)

        input_image = gr.Image(
            type="filepath",
            label="Upload Image",
            sources=["upload"],
        )

        with gr.Row():
            generate_button = gr.Button("Generate", variant="primary")
            clear_button = gr.Button("Clear")

        completed_image = gr.Image(type="pil", label="Completed Image")

        with gr.Row():
            puzzle_image = gr.Image(type="pil", label="Puzzle Template")
            legend_image = gr.Image(type="pil", label="Color Legend")

        download_bundle = gr.File(label="Download ZIP")

        generate_button.click(
            fn=on_generate,
            inputs=[input_image, temp_dir_state],
            outputs=[
                completed_image,
                puzzle_image,
                legend_image,
                download_bundle,
                temp_dir_state,
            ],
        )

        clear_button.click(
            fn=on_clear,
            inputs=[temp_dir_state],
            outputs=[
                input_image,
                completed_image,
                puzzle_image,
                legend_image,
                download_bundle,
                temp_dir_state,
            ],
        )

    return demo


def main() -> None:
    demo = build_app()
    demo.launch(show_error=True, server_port=_find_open_port())


def _create_zip_bundle(zip_path: Path, *artifact_paths: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for artifact_path in artifact_paths:
            archive.write(artifact_path, arcname=artifact_path.name)


def _import_gradio() -> Any:
    try:
        import gradio as gr
    except ImportError as exc:
        raise ImportError(
            "Gradio is required to run the web interface. Install the project "
            "dependencies with `pip install -e .` and try again."
        ) from exc

    return gr


def _register_temp_dir(temp_dir: Path) -> None:
    _ACTIVE_TEMP_DIRS.add(temp_dir)


def _sanitize_stem(stem: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._")
    return cleaned or "uploaded_image"


def _find_open_port() -> int:
    for port in range(7860, 7960):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _cleanup_registered_temp_dirs() -> None:
    for temp_dir in list(_ACTIVE_TEMP_DIRS):
        cleanup_temp_dir(temp_dir)


atexit.register(_cleanup_registered_temp_dirs)
