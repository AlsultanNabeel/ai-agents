"""Run from the project folder:  python check_embedding.py
Step 1 needs no network: it proves bad vectors are caught. Step 2 calls the real API once."""
import math
from dotenv import load_dotenv
load_dotenv()
from flask_app.utils import embeddings

print("1) Bad vectors must be rejected:")
for label, bad in [("empty list", []), ("all zeros", [0, 0, 0]), ("NaN inside", [1.0, float("nan")]),
                   ("not numbers", ["a", "b"]), ("missing (None)", None)]:
    try:
        embeddings.validate_vector(bad)
        print(f"   FAIL - accepted: {label}")
    except embeddings.EmbeddingError as error:
        print(f"   ok - {label}: {error}")

print("\n2) Real API call:")
texts = ["MSU", "Michigan State University", "banana bread recipe"]
try:
    a, b, c = embeddings.embed_texts(texts)
except embeddings.EmbeddingError as error:
    raise SystemExit(f"   FAILED (nothing would be stored): {error}")

def cosine(x, y):
    return sum(i * j for i, j in zip(x, y)) / (math.sqrt(sum(i * i for i in x)) * math.sqrt(sum(j * j for j in y)))

print(f"   model: {embeddings.current_model()}   numbers per embedding: {len(a)}")
print(f"   first 3 numbers of 'MSU': {[round(v, 4) for v in a[:3]]}")
print(f"   similarity 'MSU' vs 'Michigan State University': {cosine(a, b):.3f}")
print(f"   similarity 'MSU' vs 'banana bread recipe':        {cosine(a, c):.3f}")
