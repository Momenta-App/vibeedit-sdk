import argparse
from pathlib import Path
from vibeedit.examples import prepare_caption_example, render_example

parser = argparse.ArgumentParser(description="Render generated layout stand-in or initialize supplied video + source-time words; preserve an initialized project's corrections.")
parser.add_argument("--video", help="User supplied video (requires --words)")
parser.add_argument("--words", help="JSON {words:[{id,text,startUs,endUs}]} in normalized video time")
args = parser.parse_args()
root = Path(__file__).parent
prepare_caption_example(root, media=args.video, words=args.words)
print(render_example(root))
