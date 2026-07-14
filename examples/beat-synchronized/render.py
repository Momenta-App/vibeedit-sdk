from pathlib import Path

from vibeedit import render_example


result = render_example(Path(__file__).parent)
print(result or Path(__file__).parent / 'segmentation-unavailable.json')
