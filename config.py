import os
from dotenv import load_dotenv

load_dotenv()

TINYFISH_API_KEY = os.environ["TINYFISH_API_KEY"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
DB_PATH = "regflow.db"
OPENAI_MODEL = "gpt-4o"
SEED_URL = "https://www.acra.gov.sg"
GITHUB_REPO = "jeromepaulteoh/Shikigami"
