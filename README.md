# Color By Number

Generate **color-by-number puzzle images** from input images using Python.

This package converts a source image into:

- a **numbered puzzle template**
- a **color legend (reference palette)**
- a **completed colored mosaic**

The goal is to easily create printable **paint-by-number / color-by-number puzzles**.

---

# News: Use The UI From Terminal

You do **not** need VS Code to use the new interface. After a **one-time setup**,
you can open the UI from Terminal only and generate figures in your browser.

## One-Time Setup

1. Clone the repository:

```bash
git clone https://github.com/KeonZhao/color_by_number.git
cd color_by_number
```

2. Create a virtual environment:

```bash
python3 -m venv .venv
```

3. Activate the environment:

```bash
source .venv/bin/activate
```

4. Install the project:

```bash
pip install -e .
```

## Open The UI And Generate Figures

After the one-time setup above, later runs only need Terminal:

1. Open Terminal in the project folder:

```bash
cd /path/to/color_by_number
```

2. Activate the existing environment:

```bash
source .venv/bin/activate
```

3. Start the local UI:

```bash
color-by-number-ui
```

4. Open the local address shown in Terminal, usually:

```text
http://127.0.0.1:7860
```

5. Upload an image.
6. Click `Generate`.
7. View the completed image, puzzle template, and color legend.
8. Download the ZIP file with all generated PNG files.
9. Press `Ctrl+C` in Terminal when you want to stop the UI.

## What The UI Does

- the uploaded image is the only required input
- puzzle settings are derived automatically from the image size
- generated files are written to a temporary directory instead of `outputs/`
- the completed image is shown first, followed by the puzzle and legend
- the download ZIP contains:

```text
<image>_completed.png
<image>_legend.png
<image>_puzzle.png
```

---

# Use It In Python

You can still use this project directly as a Python package.

Install locally:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Or install from GitHub:

```bash
pip install git+https://github.com/KeonZhao/color_by_number.git
```

Main dependencies include:

- numpy
- pillow
- scikit-learn
- scikit-image
- gradio

## Quick Start

```python
from color_by_number import ColorByNumber

cbn = ColorByNumber(
    fig_path="example.jpg",
    number_of_colors=10,
    number_of_blocks=40,
    save_path="outputs"
)

# Generate puzzle template
cbn.generate_mosaic()

# Generate color legend
cbn.generate_reference_color_bar()

# Generate completed solution
cbn.complete_mosaic()

# Save the outputs
cbn.save_mosaic()
```

After running this code, the following folders will be created automatically:

```
outputs/
 ├── puzzle/
 ├── legend/
 └── solution/
```

These contain:

```
puzzle/
  mosaic_puzzle.png

legend/
  reference_color_bar.png

solution/
  mosaic_completed.png
```

- **puzzle** → numbered template to color
- **legend** → number-to-color reference
- **solution** → completed mosaic

---

# Parameters

### `fig_path`

Path to the input image.

Example:

```
fig_path="image.jpg"
```

---

### `number_of_colors`

Number of colors used in the palette.

Typical values:

```
6 – 12   simple puzzle
12 – 20  moderate detail
20+      detailed puzzle
```

---

### `number_of_blocks`

Controls the mosaic resolution.

This is the **number of blocks across the width**.

Typical values:

```
20–40   simple puzzle
40–80   moderate detail
80+     detailed puzzle
```

Higher values produce more detailed puzzles.

---

# Notes on Image Suitability

Not all images are suitable for color-by-number conversion.

Images work best when they contain:

- clear color regions
- simple backgrounds
- moderate contrast
- distinct objects

Images that may produce poor results include:

- highly textured images (grass, sand, fur)
- extremely detailed photographs
- noisy images
- images with thousands of subtle color variations

For best results, use images with **clear shapes and simple composition**.

---

# Example Use Cases

- Paint-by-number puzzles
- Coloring books
- Educational art activities
- Creative coding projects
- Image simplification experiments

## Example

### Input Image

![Input](original_figures/test_1.JPG)

### Puzzle Template

![Puzzle](outputs/puzzle/test_1.JPG_mosaic_puzzle.png)

### Color Legend

![Legend](outputs/legend/test_1.JPG_reference_color_bar.png)

### Completed Result

![Solution](outputs/solution/test_1.JPG_mosaic_completed.png)
---

# License

MIT License
