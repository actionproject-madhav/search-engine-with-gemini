"""
Querying the vector database
"""

#--- Imports
from pinecone import Pinecone
from pinecone import ServerlessSpec
import time
import voyageai
from time import sleep
import os
import requests
from tqdm.auto import tqdm

#--- API keys
print("Script Started")
PINECONE_API_KEY = os.environ.get('PINECONE_API_KEY')
VOYAGE_API_KEY = os.environ.get('VOYAGE_API_KEY')
print("PINECONE_API_KEY:", PINECONE_API_KEY)
print("VOYAGE_API_KEY:", VOYAGE_API_KEY)


# Check if API keys are set correctly
if not PINECONE_API_KEY or not VOYAGE_API_KEY:
    print("Error: API keys are missing!")
else:
    print("API keys are set.")

#--- Initialize Voyage
try:
    vo = voyageai.Client(api_key=VOYAGE_API_KEY)
    print("VoyageAI client initialized successfully.")
except Exception as e:
    print(f"Error initializing VoyageAI: {e}")
    exit()

#--- Setup Pinecone vector database
pc = Pinecone(api_key=PINECONE_API_KEY)
spec = ServerlessSpec(
    cloud="aws", region="us-east-1"
)

# connect to index
index_name = 'words'
try:
    index = pc.Index(index_name)
    print(f"Connected to Pinecone index: {index_name}")
except Exception as e:
    print(f"Error connecting to Pinecone index: {e}")
    exit()

time.sleep(1)

#--- Query code
query = "Happy Fox Day"

# Embed the query string
try:
    question_embed = vo.embed([query], model="voyage-2", input_type="document")
    print("Embedded query:", question_embed.embeddings)
except Exception as e:
    print(f"Error embedding query: {e}")
    exit()

# Retrieve the top-k similar vectors from the DB
try:
    results = index.query(
        vector=question_embed.embeddings, top_k=10, include_metadata=True
    )
    print("Query results:", results)
except Exception as e:
    print(f"Error querying Pinecone: {e}")
    exit()

texts = ["acknowldge", "acetals", "acetate"]

# Embed three words
try:
    result = vo.embed(texts, model="voyage-2", input_type="document")
    man_embed = result.embeddings[0]
    woman_embed = result.embeddings[1]
    king_embed = result.embeddings[2]
    print(f"Embedded words: man, woman, king")
except Exception as e:
    print(f"Error embedding words: {e}")
    exit()

# Compute element-wise difference between "woman" and "man"
diff_vector = [woman_embed[i] - man_embed[i] for i in range(len(man_embed))]

# Add the difference vector to the "king" embedding
query_embed = [king_embed[i] + diff_vector[i] for i in range(len(king_embed))]

# Query Pinecone with the new query vector
try:
    results = index.query(
        vector=query_embed, top_k=10, include_metadata=True
    )
    print("Query results for adjusted vector:", results)
except Exception as e:
    print(f"Error querying Pinecone with adjusted vector: {e}")
    exit()
