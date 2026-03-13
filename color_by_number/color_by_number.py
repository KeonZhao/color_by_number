from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

try:
    from sklearn.cluster import KMeans
except ImportError as e:
    raise ImportError(
        "scikit-learn is required for color quantization. "
        "Install it with: pip install scikit-learn"
    ) from e


RGBColor = Tuple[int, int, int]


class ColorByNumber:
    """
    Turn an image into a puzzle-style color-by-number puzzle.

    Workflow:
        1. generate_mosaic() -> puzzle image with numbers inside blocks
        2. generate_reference_color_bar() -> separate legend of number -> color
        3. complete_mosaic() -> revealed colored puzzle

    Important:
        The number <-> color mapping is fixed after palette extraction.
    """

    def __init__(
        self,
        fig_path: str,
        number_of_colors: int,
        number_of_blocks: int,
        save_path: Optional[str] = None,
        block_outline_color: RGBColor = (120, 120, 120),
        background_color: RGBColor = (255, 255, 255),
        random_state: int = 42,
    ) -> None:
        self.fig_path = Path(fig_path)
        self.number_of_colors = int(number_of_colors)
        self.number_of_blocks = int(number_of_blocks)  # blocks across the width
        self.save_path = Path(save_path) if save_path else None
        self.block_outline_color = block_outline_color
        self.background_color = background_color
        self.random_state = random_state

        if self.number_of_colors < 1:
            raise ValueError("number_of_colors must be at least 1.")
        if self.number_of_blocks < 1:
            raise ValueError("number_of_blocks must be at least 1.")
        if not self.fig_path.exists():
            raise FileNotFoundError(f"Image not found: {self.fig_path}")

        self.original_image: Image.Image = Image.open(self.fig_path).convert("RGB")

        # Internal state that becomes fixed after processing
        self.palette: Optional[List[RGBColor]] = None
        self.number_to_color: Optional[Dict[int, RGBColor]] = None
        self.color_to_number: Optional[Dict[RGBColor, int]] = None
        self.block_labels: Optional[np.ndarray] = None
        self.block_colors: Optional[np.ndarray] = None

        self.puzzle_image: Optional[Image.Image] = None
        self.reference_bar_image: Optional[Image.Image] = None
        self.completed_image: Optional[Image.Image] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def generate_mosaic(
        self,
        block_size: int = 40,
        margin: int = 0,
        font_path: Optional[str] = None,
        show_grid: bool = True,
    ) -> Image.Image:
        """
        Create a puzzle-style puzzle image:
        - white blocks
        - number inside each block
        - fixed number -> color dictionary

        Returns
        -------
        PIL.Image.Image
            Puzzle image.
        """
        self._prepare_model()

        font = self._get_font(block_size=block_size, font_path=font_path)
        n_rows, n_cols = self.block_labels.shape

        width = n_cols * block_size + 2 * margin
        height = n_rows * block_size + 2 * margin

        canvas = Image.new("RGB", (width, height), self.background_color)
        draw = ImageDraw.Draw(canvas)

        for r in range(n_rows):
            for c in range(n_cols):
                x0 = margin + c * block_size
                y0 = margin + r * block_size
                x1 = x0 + block_size
                y1 = y0 + block_size

                # White block for puzzle
                draw.rectangle(
                    [x0, y0, x1, y1],
                    fill=(255, 255, 255),
                    outline=self.block_outline_color if show_grid else None,
                    width=1,
                )

                label = int(self.block_labels[r, c])
                text = str(label)

                bbox = draw.textbbox((0, 0), text, font=font)
                tw = bbox[2] - bbox[0]
                th = bbox[3] - bbox[1]

                tx = x0 + (block_size - tw) / 2
                ty = y0 + (block_size - th) / 2 - 1

                draw.text((tx, ty), text, fill=(0, 0, 0), font=font)

        self.puzzle_image = canvas
        return canvas

    def generate_reference_color_bar(
        self,
        swatch_width: int = 90,
        swatch_height: int = 50,
        padding: int = 16,
        text_gap: int = 16,
        columns: int = 1,
        font_path: Optional[str] = None,
    ) -> Image.Image:
        """
        Generate a separate legend that shows:
            number -> true color

        This stays separate from the puzzle image.
        """
        self._prepare_model()

        n_items = len(self.number_to_color)
        columns = max(1, int(columns))
        rows = math.ceil(n_items / columns)

        font_size = max(14, min(24, swatch_height // 2))
        font = self._get_font_from_size(font_size, font_path=font_path)

        item_width = swatch_width + text_gap + 60
        item_height = max(swatch_height, font_size + 10)

        width = padding * 2 + columns * item_width + (columns - 1) * padding
        height = padding * 2 + rows * item_height + (rows - 1) * padding

        canvas = Image.new("RGB", (width, height), (255, 255, 255))
        draw = ImageDraw.Draw(canvas)

        for idx, number in enumerate(sorted(self.number_to_color.keys())):
            color = self.number_to_color[number]

            row = idx // columns
            col = idx % columns

            x0 = padding + col * (item_width + padding)
            y0 = padding + row * (item_height + padding)

            # color swatch
            draw.rectangle(
                [x0, y0, x0 + swatch_width, y0 + swatch_height],
                fill=color,
                outline=(0, 0, 0),
                width=1,
            )

            # text
            text = f"{number}"
            tx = x0 + swatch_width + text_gap
            ty = y0 + (swatch_height - font_size) / 2 - 2
            draw.text((tx, ty), text, fill=(0, 0, 0), font=font)

        self.reference_bar_image = canvas
        return canvas

    def complete_mosaic(
        self,
        block_size: int = 40,
        margin: int = 0,
        show_numbers: bool = False,
        show_grid: bool = True,
        font_path: Optional[str] = None,
    ) -> Image.Image:
        """
        Generate the revealed puzzle image using the same fixed
        number -> color mapping.
        """
        self._prepare_model()

        font = self._get_font(block_size=block_size, font_path=font_path)
        n_rows, n_cols = self.block_labels.shape

        width = n_cols * block_size + 2 * margin
        height = n_rows * block_size + 2 * margin

        canvas = Image.new("RGB", (width, height), self.background_color)
        draw = ImageDraw.Draw(canvas)

        for r in range(n_rows):
            for c in range(n_cols):
                x0 = margin + c * block_size
                y0 = margin + r * block_size
                x1 = x0 + block_size
                y1 = y0 + block_size

                color = tuple(map(int, self.block_colors[r, c]))
                draw.rectangle(
                    [x0, y0, x1, y1],
                    fill=color,
                    outline=self.block_outline_color if show_grid else None,
                    width=1,
                )

                if show_numbers:
                    label = int(self.block_labels[r, c])
                    text = str(label)

                    bbox = draw.textbbox((0, 0), text, font=font)
                    tw = bbox[2] - bbox[0]
                    th = bbox[3] - bbox[1]

                    tx = x0 + (block_size - tw) / 2
                    ty = y0 + (block_size - th) / 2 - 1
                    draw.text(
                        (tx, ty),
                        text,
                        fill=self._best_text_color(color),
                        font=font,
                    )

        self.completed_image = canvas
        return canvas

    def save_mosaic(
            self,
            mosaic_folder="puzzle",
            reference_folder="legend",
            result_folder="solution",
            mosaic_name="mosaic_puzzle.png",
            reference_name="reference_color_bar.png",
            completed_name="mosaic_completed.png",
    ):

        if self.save_path is None:
            raise ValueError("save_path was not provided in __init__.")

        mosaic_path = self.save_path / mosaic_folder
        reference_path = self.save_path / reference_folder
        result_path = self.save_path / result_folder

        mosaic_path.mkdir(parents=True, exist_ok=True)
        reference_path.mkdir(parents=True, exist_ok=True)
        result_path.mkdir(parents=True, exist_ok=True)

        if self.puzzle_image is not None:
            self.puzzle_image.save(mosaic_path / mosaic_name)

        if self.reference_bar_image is not None:
            self.reference_bar_image.save(reference_path / reference_name)

        if self.completed_image is not None:
            self.completed_image.save(result_path / completed_name)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _prepare_model(self) -> None:
        """
        Build the palette, number mapping, and block assignments once.
        This ensures the dictionary stays fixed across all outputs.
        """
        if self.palette is not None and self.block_labels is not None:
            return

        img_array = np.asarray(self.original_image, dtype=np.uint8)
        h, w, _ = img_array.shape

        # Determine puzzle grid size while preserving aspect ratio
        n_cols = self.number_of_blocks
        n_rows = max(1, round(h / w * n_cols))

        # Resize image to block grid, one pixel per future block
        small_img = self.original_image.resize((n_cols, n_rows), Image.Resampling.LANCZOS)
        small_array = np.asarray(small_img, dtype=np.uint8)

        # Extract fixed palette from resized image
        palette = self._extract_palette(small_array, self.number_of_colors)

        # Stable numbering:
        # sort colors by luminance, then R/G/B as tiebreak
        palette = sorted(palette, key=lambda c: (self._luminance(c), c[0], c[1], c[2]))

        self.palette = palette
        self.number_to_color = {i + 1: color for i, color in enumerate(self.palette)}
        self.color_to_number = {color: number for number, color in self.number_to_color.items()}

        # Assign each block the nearest palette color
        block_colors = np.zeros((n_rows, n_cols, 3), dtype=np.uint8)
        block_labels = np.zeros((n_rows, n_cols), dtype=np.int32)

        for r in range(n_rows):
            for c in range(n_cols):
                avg_color = tuple(map(int, small_array[r, c]))
                nearest = self._nearest_palette_color(avg_color, self.palette)
                number = self.color_to_number[nearest]

                block_colors[r, c] = np.array(nearest, dtype=np.uint8)
                block_labels[r, c] = number

        self.block_colors = block_colors
        self.block_labels = block_labels

    def _extract_palette(self, small_array: np.ndarray, n_colors: int) -> List[RGBColor]:
        """
        Use KMeans to get a representative palette.
        """
        pixels = small_array.reshape(-1, 3).astype(np.float32)

        unique_pixels = np.unique(pixels.astype(np.uint8), axis=0)
        actual_k = min(n_colors, len(unique_pixels))
        if actual_k < 1:
            raise ValueError("Could not extract any colors from the image.")

        kmeans = KMeans(
            n_clusters=actual_k,
            random_state=self.random_state,
            n_init=10,
        )
        kmeans.fit(pixels)

        centers = np.clip(np.round(kmeans.cluster_centers_), 0, 255).astype(np.uint8)
        palette = [tuple(map(int, row)) for row in centers]

        return palette

    @staticmethod
    def _nearest_palette_color(color: RGBColor, palette: List[RGBColor]) -> RGBColor:
        arr = np.array(palette, dtype=np.int16)
        c = np.array(color, dtype=np.int16)
        dists = np.sum((arr - c) ** 2, axis=1)
        idx = int(np.argmin(dists))
        return palette[idx]

    @staticmethod
    def _luminance(color: RGBColor) -> float:
        r, g, b = color
        return 0.299 * r + 0.587 * g + 0.114 * b

    @staticmethod
    def _best_text_color(color: RGBColor) -> RGBColor:
        return (0, 0, 0) if ColorByNumber._luminance(color) > 150 else (255, 255, 255)

    @staticmethod
    def _get_font(block_size: int, font_path: Optional[str] = None) -> ImageFont.ImageFont:
        font_size = max(10, block_size // 3)
        return ColorByNumber._get_font_from_size(font_size, font_path)

    @staticmethod
    def _get_font_from_size(size: int, font_path: Optional[str] = None) -> ImageFont.ImageFont:
        try:
            if font_path is not None:
                return ImageFont.truetype(font_path, size=size)
            return ImageFont.truetype("arial.ttf", size=size)
        except Exception:
            return ImageFont.load_default()