from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from PIL import Image

from color_by_number.web_app import generate_artifacts


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_IMAGE = REPO_ROOT / "original_figures" / "test_1.JPG"


class GenerateArtifactsTests(unittest.TestCase):
    def test_generate_artifacts_creates_three_images_and_zip_bundle(self) -> None:
        artifacts = generate_artifacts(SAMPLE_IMAGE)

        try:
            self.assertEqual(artifacts.stem, "test_1")
            self.assertTrue(artifacts.temp_dir.exists())
            self.assertTrue(artifacts.puzzle_path.exists())
            self.assertTrue(artifacts.legend_path.exists())
            self.assertTrue(artifacts.completed_path.exists())
            self.assertTrue(artifacts.zip_path.exists())

            with zipfile.ZipFile(artifacts.zip_path) as archive:
                self.assertEqual(
                    sorted(archive.namelist()),
                    [
                        "test_1_completed.png",
                        "test_1_legend.png",
                        "test_1_puzzle.png",
                    ],
                )

            self.assertGreater(artifacts.completed_image.size[0], 0)
            self.assertGreater(artifacts.completed_image.size[1], 0)
            self.assertGreater(artifacts.puzzle_image.size[0], 0)
            self.assertGreater(artifacts.legend_image.size[1], 0)
        finally:
            artifacts.cleanup()

        self.assertFalse(artifacts.temp_dir.exists())

    def test_generate_artifacts_requires_an_uploaded_image(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "Please upload an image to generate a color-by-number set.",
        ):
            generate_artifacts(None)

    def test_generate_artifacts_rejects_images_smaller_than_twenty_pixels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            image_path = Path(tmp_dir) / "tiny.png"
            Image.new("RGB", (19, 25), color=(255, 0, 0)).save(image_path)

            with self.assertRaisesRegex(
                ValueError,
                "Please upload an image that is at least 20px on both sides.",
            ):
                generate_artifacts(image_path)


if __name__ == "__main__":
    unittest.main()
