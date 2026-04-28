import open_clip
import torch
import csv
import numpy as np
import os
import hashlib
import json
import requests
from PIL import Image
from loguru import logger

from src.database import SessionLocal
from src.db_service import get_all_categories

from src.config import CLIP_Settings

class ClipTagger:
    settings = CLIP_Settings()
    CSV_PATH = settings.CSV_PATH
    NPY_PATH = settings.NPY_PATH
    TAGS_LIST_PATH = settings.TAGS_LIST_PATH
    TAGS_CLIP_THRESHOLD = settings.TAGS_CLIP_THRESHOLD
    VOCAB_URL = settings.VOCAB_URL
    CATEGORIES_NPY_PATH = settings.CATEGORIES_NPY_PATH
    CATEGORIES_HASH_PATH = settings.CATEGORIES_HASH_PATH
    CATEGORIES_CLIP_THRESHOLD = settings.CATEGORIES_CLIP_THRESHOLD
    

    def __init__(self):
        self.model_name = self.settings.CLIP_MODEL
        self.pretrained = self.settings.PRETRAINED
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = None
        self.preprocess = None
        self.tags_features = None
        self.tags = []
        self.categories_features = None
        self.categories = []


    def _normalize_tags(self, tags: list[str]) -> list[str]:
        return list(set(t.lower().strip() for t in tags if t.strip()))

    def download_vocabulary(self) -> list[str]:
        os.makedirs(os.path.dirname(self.CSV_PATH), exist_ok=True)
        logger.info(f"Downloading Open Images Vocabulary from {self.VOCAB_URL}...")
        try:
            response = requests.get(self.VOCAB_URL)
            logger.info(f"Response: {response}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to download vocabulary: {e}")
            raise Exception(f"Failed to download vocabulary: {e}")
        if response.status_code == 200:
            try:
                with open(self.CSV_PATH, "w") as f:
                    f.write(response.text)
                logger.info(f"Vocabulary saved to {self.CSV_PATH}")
            except Exception as e:
                logger.error(f"Failed to save vocabulary: {e}")
                raise Exception(f"Failed to save vocabulary: {e}")
        else:
            logger.error(f"Failed to download vocabulary: {response.status_code}")
            raise Exception(f"Failed to download vocabulary: {response.status_code}")
        
        tags = []
        with open(self.CSV_PATH, "r") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) > 1:
                    tags.append(row[1])
        
        normalized = self._normalize_tags(tags)
        with open(self.TAGS_LIST_PATH, "w") as f:
            for t in normalized:
                f.write(f"{t}\n")
        logger.info("Vocabulary downloaded and normalized.")
        return normalized

    def compute_embeddings_tags(self, tags: list[str]):
        self.load_model()
        logger.info(f"Computing embeddings for {len(tags)} tags...")
        batch_size = 128
        all_features = []
        
        with torch.no_grad():
            for i in range(0, len(tags), batch_size):
                batch = tags[i:i+batch_size]
                tokens = open_clip.tokenize(batch).to(self.device)
                features = self.model.encode_text(tokens)
                norm = features.norm(dim=-1, keepdim=True)
                features = features / norm
                all_features.append(features.detach().cpu().numpy())
        
        self.tags_features = np.concatenate(all_features, axis=0)
        np.save(self.NPY_PATH, self.tags_features)

    def compute_categories_hash(self, categories: list[dict]) -> str:
        """
        categories = [
            {"id": 1, "name": "food", "prompt": "..."},
            ...
        ]
        """
        categories = sorted(categories, key=lambda x: x["id"])
        data = json.dumps(categories, sort_keys=True)
        return hashlib.md5(data.encode()).hexdigest()

    def is_cache_category_valid(self, categories, hash_path):
        if not os.path.exists(hash_path):
            return False
        current_hash = self.compute_categories_hash(categories)
        with open(hash_path, "r") as f:
            saved_hash = f.read().strip()

        return current_hash == saved_hash

    def save_category_cache(self, features, categories, npy_path, hash_path):
        np.save(npy_path, features)
        current_hash = self.compute_categories_hash(categories)
        with open(hash_path, "w") as f:
            f.write(current_hash)

    def load_or_compute_categories(self):
        """Load or compute categories embeddings"""
        logger.info("Loading or computing categories embeddings...")
        self.load_model()
        db = SessionLocal()
        rows = get_all_categories(db)
        db.close()
        logger.info(f"Found {len(rows)} categories.")
        if not rows:
            raise ValueError("No categories found in DB")

        categories = [
            {"id": c.id, "name": c.name, "prompt": c.prompt}
            for c in rows
        ]
        
        logger.info(f"Categories[0]: {categories[0]}")

        if (
            os.path.exists(self.CATEGORIES_NPY_PATH)
            and self.is_cache_category_valid(
                categories, self.CATEGORIES_HASH_PATH
            )
        ):
            self.categories_features = torch.from_numpy(
                np.load(self.CATEGORIES_NPY_PATH)
            ).float().to(self.device)

            logger.info("Loaded categories from cache ✅")
        else:
            logger.info("Recomputing categories embeddings 🔄")

            names = [c["name"] for c in categories]
            prompts = [c["prompt"] for c in categories]
            self.compute_embeddings_categories(names, prompts)
            self.save_category_cache(
                self.categories_features.cpu().numpy(),
                categories,
                self.CATEGORIES_NPY_PATH,
                self.CATEGORIES_HASH_PATH
            )
        self.categories = categories

    def compute_embeddings_categories(self, names: list[str], prompts: list[str]):
        self.load_model()

        batch_size = 128
        all_features = []

        with torch.no_grad():
            for i in range(0, len(prompts), batch_size):
                batch = prompts[i:i+batch_size]

                tokens = open_clip.tokenize(batch).to(self.device)
                features = self.model.encode_text(tokens)

                features /= features.norm(dim=-1, keepdim=True)

                all_features.append(features)

        self.categories_features = torch.cat(all_features, dim=0)

    def download(self):
        logger.info(f"Downloading {self.model_name}...")
        open_clip.create_model_and_transforms(self.model_name, self.pretrained)
        logger.info(f"Model {self.model_name} downloaded.")
        if not os.path.exists(self.NPY_PATH):
            logger.info(f"Downloading tags...")
            tags = self.download_vocabulary()
            logger.info(f"Tags downloaded.")
            logger.info(f"Computing embeddings for {len(tags)} tags...")
            self.compute_embeddings_tags(tags)
            logger.info(f"Embeddings computed.")
        if not os.path.exists(self.CATEGORIES_NPY_PATH):
            logger.info(f"Loading or computing categories...")
            self.load_or_compute_categories()
            logger.info(f"Categories loaded or computed.")

    def load_model(self):
        """
        Load model from disk if not already loaded
        """
        self.model, _, self.preprocess = open_clip.create_model_and_transforms(
            self.model_name, self.pretrained, device=self.device
        )
        self.model.eval()
        logger.info(f"DEBUG: ClipTagger.load_model() model loaded")

    def load_tags(self):
        """
        Load tags from disk if not already loaded
        """
        if self.tags_features is None and os.path.exists(self.NPY_PATH):
            self.tags_features = np.load(self.NPY_PATH)
        
        if not self.tags and os.path.exists(self.TAGS_LIST_PATH):
            with open(self.TAGS_LIST_PATH, "r") as f:
                self.tags = [line.strip() for line in f]

    def find_tags(self, filepath: str, top_k: int = 20) -> list[tuple[str, float]]:
        self.load_tags()
        self.load_model()
        if self.tags_features is None or not self.tags:
            return []
        image = self.preprocess(Image.open(filepath)).unsqueeze(0).to(self.device)
        with torch.no_grad():
            image_features = self.model.encode_image(image)
            img_norm = image_features.norm(dim=-1, keepdim=True)
            image_features = image_features / img_norm
            similarities = (image_features.cpu().numpy() @ self.tags_features.T).squeeze()
            top_indices = similarities.argsort()[-top_k:][::-1]
            return [(self.tags[i], float(similarities[i])) for i in top_indices if similarities[i] > self.TAGS_CLIP_THRESHOLD]

    def categorize(self, filepath: str, top_k: int = 5) -> list[tuple[str, float]]:
        """Dynamic Zero-Shot categorization against custom category list."""
        logger.info(f"DEBUG: ClipTagger.categorize() called for {filepath}")
        self.load_or_compute_categories()
        logger.info(f"DEBUG: ClipTagger.categorize() categories loaded")
        self.load_model()
        image = self.preprocess(Image.open(filepath)).unsqueeze(0).to(self.device)
        logger.info(f"DEBUG: ClipTagger.categorize() image loaded")
        with torch.no_grad():
            image_features = self.model.encode_image(image)
            image_features /= image_features.norm(dim=-1, keepdim=True)
            logger.info(f"DEBUG: ClipTagger.categorize() image features encoded")
            similarities = (image_features @ self.categories_features.T).squeeze(0)
            # threshold first
            mask = similarities > self.CATEGORIES_CLIP_THRESHOLD
            filtered_indices = mask.nonzero(as_tuple=True)[0]
            logger.info(f"DEBUG: ClipTagger.categorize() filtered indices: {filtered_indices}")

            if len(filtered_indices) == 0:
                return []

            filtered_scores = similarities[filtered_indices]
            logger.info(f"DEBUG: ClipTagger.categorize() filtered scores calculated")

            topk = torch.topk(filtered_scores, min(top_k, len(filtered_scores)))
            logger.info(f"DEBUG: ClipTagger.categorize() topk calculated")
            results = [
                (
                    self.categories[filtered_indices[i]]["id"],
                    self.categories[filtered_indices[i]]["name"],
                    float(topk.values[j])
                ) for j, i in enumerate(topk.indices)
            ]
            logger.info(f"DEBUG: ClipTagger.categorize() results: {results}")
        return results