"""
Example of embedding a text string using VoyageAI
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
PINECONE_API_KEY = os.environ.get('PINECONE_API_KEY')
VOYAGE_API_KEY = os.environ.get('VOYAGE_API_KEY')

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

#--- Calculate some example embeddings
texts = ["Happy Fox Day"]
try:
    result = vo.embed(texts, model="voyage-2", input_type="document")
    print("Example embeddings:", result.embeddings[0])
except Exception as e:
    print(f"Error embedding text: {e}")
    exit()

#--- Setup Pinecone vector database
pc = Pinecone(api_key=PINECONE_API_KEY)
spec = ServerlessSpec(
    cloud="aws", region="us-east-1"
)

#--- Create a new vector database
index_name = 'words'
existing_indexes = [
    index_info["name"] for index_info in pc.list_indexes()
]

# Check if index already exists (it shouldn't if this is first time)
if index_name not in existing_indexes:
    print(f"Creating index: {index_name}")
    try:
        pc.create_index(
            index_name,
            dimension=1024,  # dimensionality of voyage-2 embeddings
            metric='dotproduct',
            spec=spec
        )
        print(f"Index {index_name} created.")
    except Exception as e:
        print(f"Error creating index: {e}")
        exit()

    # wait for index to be initialized
    while not pc.describe_index(index_name).status['ready']:
        time.sleep(1)

# connect to index
try:
    index = pc.Index(index_name)
    print("Connected to Pinecone index.")
except Exception as e:
    print(f"Error connecting to Pinecone index: {e}")
    exit()

time.sleep(1)

#--- Get the words.txt file
url = "https://raw.githubusercontent.com/dansmyers/AI/main/Labs/4-Embeddings/words.txt"
response = requests.get(url)
if response.status_code == 200:
    words_string = response.text
    words = words_string.split('\n')
    print(f"Loaded {len(words)} words from words.txt.")
else:
    print(f"Error fetching words.txt: {response.status_code}")
    exit()

#--- Populate the vector database with the list of words
batch_size = 100
for i in tqdm(range(0, len(words), batch_size)):
    i_end = min(len(words), i + batch_size)
    words_batch = words[i:i_end]
    print(f"Upserting batch {i} to {i_end}: {words_batch}")

    # Embed each batch of words
    done = False
    while not done:
        try:
            res = vo.embed(words_batch, model="voyage-2", input_type="document")
            done = True
        except Exception as e:
            print(f"Error embedding batch: {e}")
            sleep(5)

    embeds = [record for record in res.embeddings]
    ids_batch = [f"word_{idx}" for idx in range(i, i_end)]
    metadata_batch = [{'word': word} for word in words_batch]

    to_upsert = list(zip(ids_batch, embeds, metadata_batch))

    # upsert to Pinecone
    try:
        index.upsert(vectors=to_upsert)
        print(f"Upserted batch {i} to {i_end}.")
    except Exception as e:
        print(f"Error upserting batch: {e}")
        exit()

# After completing the upload, the DB should contain vectors
try:
    print("Pinecone index stats:", index.describe_index_stats())
except Exception as e:
    print(f"Error fetching Pinecone index stats: {e}")
