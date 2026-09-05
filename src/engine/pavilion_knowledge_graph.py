import json
import os
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

KG_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "pavilion_knowledge_graph"


class PavilionKnowledgeGraph:
    """
    Pavilion Editorial Tone, Syntax, and Vocabulary Knowledge Graph.
    Ensures both AI generated prose and deterministic template posts
    authentically mimic Pavilion Sports' distinctive newsroom voice.
    """

    def __init__(self):
        self.ontology = self._load_json("ontology.json")
        self.vocabulary = self._load_json("vocabulary_lexicon.json")
        self.tone_matrix = self._load_json("tone_matrix.json")
        self.syntax_templates = self._load_json("syntax_templates.json")

    def _load_json(self, filename: str) -> Dict[str, Any]:
        file_path = KG_DIR / filename
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading {filename}: {e}")
        return {}

    def get_system_prompt_instruction(self) -> str:
        """Constructs an authoritative system prompt embedding Pavilion's editorial identity and vocabulary."""
        return (
            "You are a Senior Football Journalist writing for Pavilion Sports (প্যাভিলিয়ন স্পোর্টস ডেস্ক 🇧🇩), "
            "Bangladesh's premier digital sports newsroom.\n\n"
            "Editorial Voice & Language Rules:\n"
            "1. Authentic Bengali Football Idioms: Use natural sports terms like 'চালকের আসনে বসালেন', 'ব্যবধান দ্বিগুণ করলেন', 'ম্যাচে নাটকীয় সমতা ফেরালেন', 'স্নায়ুচাপের লড়াই', 'ক্লিনিক্যাল ফিনিশ', 'জাদুকরী দূরপাল্লার শট'.\n"
            "2. Scoreline Transition Discipline:\n"
            "   - 0-0 -> 1-0: 'এগিয়ে গেল'\n"
            "   - 1-0 -> 1-1: 'সমতায় ফিরল / নাটকীয় সমতা ফেরালেন'\n"
            "   - 1-0 -> 2-0: 'ব্যবধান দ্বিগুণ করল'\n"
            "   - 1-1 -> 2-1: 'আবারও এগিয়ে গেল / লিড পুনরুদ্ধার করল'\n"
            "   - 2-0 -> 2-1: 'ব্যবধান কমাল'\n"
            "3. Pacing: High energy, punchy opening hook, concise description of assist provider + finish technique + match momentum.\n"
            "4. Sign-off with 'প্যাভিলিয়ন স্পোর্টস ডেস্ক 🇧🇩'."
        )

    def get_momentum_phrase(self, state_key: str) -> str:
        verbs = self.vocabulary.get("momentum_verbs", {})
        return verbs.get(state_key, "দলের হয়ে লক্ষ্যভেদ করলেন")


global_pavilion_kg = PavilionKnowledgeGraph()
