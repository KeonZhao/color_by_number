from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont
import colorsys

from sklearn.cluster import KMeans
from skimage.color import rgb2lab, lab2rgb


RGBColor = Tuple[int, int, int]


class ColorByNumber:

    def __init__(
        self,
        fig_path: str,
        number_of_colors: int,
        number_of_blocks: int,
        save_path: Optional[str] = None,
        block_outline_color: RGBColor = (180, 180, 180),
        background_color: RGBColor = (255, 255, 255),
        random_state: int = 42,
    ) -> None:

        self.fig_path = Path(fig_path)
        self.number_of_colors = int(number_of_colors)
        self.number_of_blocks = int(number_of_blocks)
        self.save_path = Path(save_path) if save_path else None
        self.block_outline_color = block_outline_color
        self.background_color = background_color
        self.random_state = random_state

        if not self.fig_path.exists():
            raise FileNotFoundError(self.fig_path)

        self.original_image: Image.Image = Image.open(self.fig_path).convert("RGB")

        self.palette: Optional[List[RGBColor]] = None
        self.number_to_color: Optional[Dict[int, RGBColor]] = None
        self.color_to_number: Optional[Dict[RGBColor, int]] = None

        self.block_labels: Optional[np.ndarray] = None
        self.block_colors: Optional[np.ndarray] = None

        self.puzzle_image: Optional[Image.Image] = None
        self.reference_bar_image: Optional[Image.Image] = None
        self.completed_image: Optional[Image.Image] = None

    # ==========================================================
    # PUBLIC API
    # ==========================================================

    def generate_mosaic(
        self,
        block_size: int = 40,
        margin: int = 0,
        font_path: Optional[str] = None,
        show_grid: bool = True,
    ) -> Image.Image:

        self._prepare_model()

        font = self._get_font(block_size, font_path)
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

                draw.rectangle(
                    [x0, y0, x1, y1],
                    fill=(255, 255, 255),
                    outline=self.block_outline_color if show_grid else None,
                )

                label = str(int(self.block_labels[r, c]))

                bbox = draw.textbbox((0, 0), label, font=font)
                tw = bbox[2] - bbox[0]
                th = bbox[3] - bbox[1]

                draw.text(
                    (x0 + (block_size - tw) / 2, y0 + (block_size - th) / 2),
                    label,
                    fill=(0, 0, 0),
                    font=font,
                )

        self.puzzle_image = canvas
        return canvas

    def generate_reference_color_bar(
        self,
        swatch_width: int = 90,
        swatch_height: int = 50,
        padding: int = 16,
        text_gap: int = 16,
        columns: int = 1,
    ) -> Image.Image:

        self._prepare_model()

        n_items = len(self.number_to_color)
        rows = math.ceil(n_items / columns)

        item_width = swatch_width + text_gap + 60
        item_height = swatch_height

        width = padding * 2 + columns * item_width
        height = padding * 2 + rows * (item_height + padding)

        canvas = Image.new("RGB", (width, height), (255, 255, 255))
        draw = ImageDraw.Draw(canvas)

        font = self._get_font_from_size(20)

        for idx, number in enumerate(sorted(self.number_to_color)):

            color = self.number_to_color[number]

            row = idx // columns
            col = idx % columns

            x0 = padding + col * item_width
            y0 = padding + row * (item_height + padding)

            draw.rectangle(
                [x0, y0, x0 + swatch_width, y0 + swatch_height],
                fill=color,
                outline=(0, 0, 0),
            )

            draw.text(
                (x0 + swatch_width + text_gap, y0 + swatch_height / 4),
                str(number),
                fill=(0, 0, 0),
                font=font,
            )

        self.reference_bar_image = canvas
        return canvas

    def complete_mosaic(
        self,
        block_size: int = 40,
        margin: int = 0,
        show_numbers: bool = False,
    ) -> Image.Image:

        self._prepare_model()

        font = self._get_font(block_size)
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
                    outline=self.block_outline_color,
                )

                if show_numbers:

                    label = str(int(self.block_labels[r, c]))

                    bbox = draw.textbbox((0, 0), label, font=font)
                    tw = bbox[2] - bbox[0]
                    th = bbox[3] - bbox[1]

                    draw.text(
                        (x0 + (block_size - tw) / 2, y0 + (block_size - th) / 2),
                        label,
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

    # ==========================================================
    # PALETTE + MODEL
    # ==========================================================

    def _prepare_model(self):

        if self.palette is not None:
            return

        img = np.asarray(self.original_image)

        h, w = img.shape[:2]

        n_cols = self.number_of_blocks
        n_rows = max(1, round(h / w * n_cols))

        small = np.asarray(
            self.original_image.resize((n_cols, n_rows), Image.Resampling.LANCZOS)
        )

        palette = self._extract_palette(small, self.number_of_colors)

        palette = sorted(
            palette,
            key=lambda c: colorsys.rgb_to_hsv(c[0]/255, c[1]/255, c[2]/255)[0]
        )

        self.palette = palette
        self.number_to_color = {i + 1: c for i, c in enumerate(palette)}
        self.color_to_number = {c: i + 1 for i, c in enumerate(palette)}

        block_colors = np.zeros((n_rows, n_cols, 3), dtype=np.uint8)
        block_labels = np.zeros((n_rows, n_cols), dtype=int)

        for r in range(n_rows):
            for c in range(n_cols):

                color = tuple(small[r, c])

                nearest = self._nearest_palette_color(color, palette)

                block_colors[r, c] = nearest
                block_labels[r, c] = self.color_to_number[nearest]

        self.block_colors = block_colors
        self.block_labels = block_labels

    def _extract_palette(self, small_array, n_colors):

        img = small_array / 255.0

        lab = rgb2lab(img)
        pixels = lab.reshape(-1, 3)

        kmeans = KMeans(
            n_clusters=n_colors,
            random_state=self.random_state,
            n_init=20
        )

        kmeans.fit(pixels)

        centers = kmeans.cluster_centers_

        palette = []

        for lab_color in centers:

            rgb = lab2rgb(lab_color.reshape(1, 1, 3))[0, 0]
            rgb = np.clip(rgb * 255, 0, 255).astype(int)

            palette.append(tuple(rgb))

        return self._refine_palette(palette)

    def _refine_palette(self, palette):

        refined = []

        for r, g, b in palette:

            r, g, b = r/255, g/255, b/255
            h, s, v = colorsys.rgb_to_hsv(r, g, b)

            s = max(0.35, min(s, 0.85))
            v = max(0.45, min(v, 0.9))

            r2, g2, b2 = colorsys.hsv_to_rgb(h, s, v)

            refined.append(
                (int(r2*255), int(g2*255), int(b2*255))
            )

        return refined

    # ==========================================================
    # UTILITIES
    # ==========================================================

    @staticmethod
    def _nearest_palette_color(color, palette):

        arr = np.array(palette)
        c = np.array(color)

        d = np.sum((arr - c) ** 2, axis=1)
        return palette[int(np.argmin(d))]

    @staticmethod
    def _best_text_color(color):

        r, g, b = color
        luminance = 0.299*r + 0.587*g + 0.114*b

        return (0,0,0) if luminance > 150 else (255,255,255)

    @staticmethod
    def _get_font(block_size, font_path=None):

        size = max(10, block_size // 3)
        return ColorByNumber._get_font_from_size(size, font_path)

    @staticmethod
    def _get_font_from_size(size, font_path=None):

        try:
            if font_path:
                return ImageFont.truetype(font_path, size)
            return ImageFont.truetype("arial.ttf", size)
        except:
            return ImageFont.load_default()