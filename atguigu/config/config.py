from dotenv import load_dotenv
import os

load_dotenv()


class MineruConfig:
    mineru_token = os.getenv("mineru_token")
    mineru_base_url = os.getenv("mineru_base_url")
