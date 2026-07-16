"""
Skill Taxonomy Interface with CS Bagrut Implementation.

Provides an abstract interface for skill taxonomies and a concrete
implementation for Israeli Computer Science Bagrut curriculum.

Architecture:
- SkillTaxonomy: Abstract base class for any skill taxonomy
- CSBagrutTaxonomy: Hardcoded MVP implementation
- Future: JSONFileTaxonomy, DatabaseTaxonomy (same interface)

Usage:
    taxonomy = CSBagrutTaxonomy()
    skill = taxonomy.get_skill("cs.loops.for")
    if taxonomy.validate_skill_id("cs.arrays.1d"):
        # Skill exists in taxonomy
"""
from abc import ABC, abstractmethod
from typing import List, Optional

from ..schemas.ontology_types import SkillTarget


class SkillTaxonomy(ABC):
    """
    Abstract interface for skill taxonomies.
    
    Implementations can be hardcoded (MVP), file-based, or database-backed.
    The interface remains consistent across all.
    """
    
    @abstractmethod
    def get_skill(self, skill_id: str) -> Optional[SkillTarget]:
        """Get a skill by ID, or None if not found."""
        pass
    
    @abstractmethod
    def get_children(self, skill_id: str) -> List[SkillTarget]:
        """Get child skills of a parent skill."""
        pass
    
    @abstractmethod
    def validate_skill_id(self, skill_id: str) -> bool:
        """Check if a skill ID exists in the taxonomy."""
        pass
    
    @abstractmethod
    def get_all_skills(self) -> List[SkillTarget]:
        """Get all skills in the taxonomy."""
        pass


class CSBagrutTaxonomy(SkillTaxonomy):
    """
    Hardcoded CS Bagrut taxonomy for MVP.
    
    Covers the core Israeli high school CS curriculum topics.
    Structured hierarchically: cs.{topic}.{subtopic}
    
    Phase 2: Replace with JSONFileTaxonomy for easier updates.
    """
    
    # Skill definitions organized by topic
    SKILLS = {
        # ===== LOOPS =====
        "cs.loops": SkillTarget(id="cs.loops", name="לולאות", priority="primary"),
        "cs.loops.for": SkillTarget(id="cs.loops.for", name="לולאת for", priority="primary"),
        "cs.loops.while": SkillTarget(id="cs.loops.while", name="לולאת while", priority="primary"),
        "cs.loops.nested": SkillTarget(id="cs.loops.nested", name="לולאות מקוננות", priority="primary"),
        "cs.loops.termination": SkillTarget(id="cs.loops.termination", name="תנאי עצירה", priority="primary"),
        
        # ===== ARRAYS =====
        "cs.arrays": SkillTarget(id="cs.arrays", name="מערכים", priority="primary"),
        "cs.arrays.1d": SkillTarget(id="cs.arrays.1d", name="מערך חד-ממדי", priority="primary"),
        "cs.arrays.2d": SkillTarget(id="cs.arrays.2d", name="מערך דו-ממדי", priority="primary"),
        "cs.arrays.traversal": SkillTarget(id="cs.arrays.traversal", name="מעבר על מערך", priority="primary"),
        "cs.arrays.search": SkillTarget(id="cs.arrays.search", name="חיפוש במערך", priority="primary"),
        "cs.arrays.sort": SkillTarget(id="cs.arrays.sort", name="מיון מערך", priority="primary"),
        
        # ===== OOP =====
        "cs.oop": SkillTarget(id="cs.oop", name="תכנות מונחה עצמים", priority="primary"),
        "cs.oop.class": SkillTarget(id="cs.oop.class", name="הגדרת מחלקה", priority="primary"),
        "cs.oop.constructor": SkillTarget(id="cs.oop.constructor", name="בנאי", priority="primary"),
        "cs.oop.fields": SkillTarget(id="cs.oop.fields", name="שדות", priority="primary"),
        "cs.oop.methods": SkillTarget(id="cs.oop.methods", name="מתודות", priority="primary"),
        "cs.oop.encapsulation": SkillTarget(id="cs.oop.encapsulation", name="כימוס", priority="primary"),
        "cs.oop.inheritance": SkillTarget(id="cs.oop.inheritance", name="ירושה", priority="primary"),
        "cs.oop.polymorphism": SkillTarget(id="cs.oop.polymorphism", name="פולימורפיזם", priority="primary"),
        "cs.oop.interfaces": SkillTarget(id="cs.oop.interfaces", name="ממשקים", priority="primary"),
        
        # ===== FUNCTIONS =====
        "cs.functions": SkillTarget(id="cs.functions", name="פונקציות", priority="primary"),
        "cs.functions.definition": SkillTarget(id="cs.functions.definition", name="הגדרת פונקציה", priority="primary"),
        "cs.functions.parameters": SkillTarget(id="cs.functions.parameters", name="פרמטרים", priority="primary"),
        "cs.functions.return": SkillTarget(id="cs.functions.return", name="ערך מוחזר", priority="primary"),
        "cs.functions.recursion": SkillTarget(id="cs.functions.recursion", name="רקורסיה", priority="primary"),
        
        # ===== CONDITIONALS =====
        "cs.conditionals": SkillTarget(id="cs.conditionals", name="תנאים", priority="primary"),
        "cs.conditionals.if": SkillTarget(id="cs.conditionals.if", name="משפט if", priority="primary"),
        "cs.conditionals.else": SkillTarget(id="cs.conditionals.else", name="משפט else", priority="primary"),
        "cs.conditionals.switch": SkillTarget(id="cs.conditionals.switch", name="משפט switch", priority="primary"),
        "cs.conditionals.logical": SkillTarget(id="cs.conditionals.logical", name="אופרטורים לוגיים", priority="primary"),
        
        # ===== DATA STRUCTURES =====
        "cs.datastructures": SkillTarget(id="cs.datastructures", name="מבני נתונים", priority="primary"),
        "cs.datastructures.stack": SkillTarget(id="cs.datastructures.stack", name="מחסנית", priority="primary"),
        "cs.datastructures.queue": SkillTarget(id="cs.datastructures.queue", name="תור", priority="primary"),
        "cs.datastructures.linkedlist": SkillTarget(id="cs.datastructures.linkedlist", name="רשימה מקושרת", priority="primary"),
        "cs.datastructures.tree": SkillTarget(id="cs.datastructures.tree", name="עץ", priority="primary"),
        "cs.datastructures.bst": SkillTarget(id="cs.datastructures.bst", name="עץ חיפוש בינארי", priority="primary"),
        
        # ===== ALGORITHMS =====
        "cs.algorithms": SkillTarget(id="cs.algorithms", name="אלגוריתמים", priority="primary"),
        "cs.algorithms.complexity": SkillTarget(id="cs.algorithms.complexity", name="סיבוכיות", priority="primary"),
        "cs.algorithms.search.linear": SkillTarget(id="cs.algorithms.search.linear", name="חיפוש ליניארי", priority="primary"),
        "cs.algorithms.search.binary": SkillTarget(id="cs.algorithms.search.binary", name="חיפוש בינארי", priority="primary"),
        "cs.algorithms.sort.bubble": SkillTarget(id="cs.algorithms.sort.bubble", name="מיון בועות", priority="primary"),
        "cs.algorithms.sort.selection": SkillTarget(id="cs.algorithms.sort.selection", name="מיון בחירה", priority="primary"),
        "cs.algorithms.sort.insertion": SkillTarget(id="cs.algorithms.sort.insertion", name="מיון הכנסה", priority="primary"),
        "cs.algorithms.sort.merge": SkillTarget(id="cs.algorithms.sort.merge", name="מיון מיזוג", priority="primary"),
        
        # ===== INPUT/OUTPUT =====
        "cs.io": SkillTarget(id="cs.io", name="קלט/פלט", priority="primary"),
        "cs.io.input": SkillTarget(id="cs.io.input", name="קלט", priority="primary"),
        "cs.io.output": SkillTarget(id="cs.io.output", name="פלט", priority="primary"),
        "cs.io.files": SkillTarget(id="cs.io.files", name="קבצים", priority="primary"),
        
        # ===== SYNTAX (Trivial) =====
        "cs.syntax": SkillTarget(id="cs.syntax", name="תחביר", priority="trivial"),
        "cs.syntax.basic": SkillTarget(id="cs.syntax.basic", name="תחביר בסיסי", priority="trivial"),
        "cs.syntax.naming": SkillTarget(id="cs.syntax.naming", name="שמות משתנים", priority="trivial"),
        "cs.syntax.comments": SkillTarget(id="cs.syntax.comments", name="הערות", priority="trivial"),
        "cs.syntax.indentation": SkillTarget(id="cs.syntax.indentation", name="הזחה", priority="trivial"),
    }
    
    # Parent-child relationships for hierarchy navigation
    _CHILDREN = {
        "cs.loops": ["cs.loops.for", "cs.loops.while", "cs.loops.nested", "cs.loops.termination"],
        "cs.arrays": ["cs.arrays.1d", "cs.arrays.2d", "cs.arrays.traversal", "cs.arrays.search", "cs.arrays.sort"],
        "cs.oop": ["cs.oop.class", "cs.oop.constructor", "cs.oop.fields", "cs.oop.methods", 
                   "cs.oop.encapsulation", "cs.oop.inheritance", "cs.oop.polymorphism", "cs.oop.interfaces"],
        "cs.functions": ["cs.functions.definition", "cs.functions.parameters", "cs.functions.return", "cs.functions.recursion"],
        "cs.conditionals": ["cs.conditionals.if", "cs.conditionals.else", "cs.conditionals.switch", "cs.conditionals.logical"],
        "cs.datastructures": ["cs.datastructures.stack", "cs.datastructures.queue", "cs.datastructures.linkedlist", 
                             "cs.datastructures.tree", "cs.datastructures.bst"],
        "cs.algorithms": ["cs.algorithms.complexity", "cs.algorithms.search.linear", "cs.algorithms.search.binary",
                         "cs.algorithms.sort.bubble", "cs.algorithms.sort.selection", "cs.algorithms.sort.insertion", 
                         "cs.algorithms.sort.merge"],
        "cs.io": ["cs.io.input", "cs.io.output", "cs.io.files"],
        "cs.syntax": ["cs.syntax.basic", "cs.syntax.naming", "cs.syntax.comments", "cs.syntax.indentation"],
    }
    
    def get_skill(self, skill_id: str) -> Optional[SkillTarget]:
        """Get a skill by ID, or None if not found."""
        return self.SKILLS.get(skill_id)
    
    def get_children(self, skill_id: str) -> List[SkillTarget]:
        """Get child skills of a parent skill."""
        child_ids = self._CHILDREN.get(skill_id, [])
        return [self.SKILLS[cid] for cid in child_ids if cid in self.SKILLS]
    
    def validate_skill_id(self, skill_id: str) -> bool:
        """Check if a skill ID exists in the taxonomy."""
        return skill_id in self.SKILLS
    
    def get_all_skills(self) -> List[SkillTarget]:
        """Get all skills in the taxonomy."""
        return list(self.SKILLS.values())
    
    def get_primary_skills(self) -> List[SkillTarget]:
        """Get only primary (non-trivial) skills."""
        return [s for s in self.SKILLS.values() if s.priority == "primary"]
    
    def get_trivial_skills(self) -> List[SkillTarget]:
        """Get only trivial skills (syntax, formatting)."""
        return [s for s in self.SKILLS.values() if s.priority == "trivial"]


# Default taxonomy instance
_default_taxonomy: Optional[SkillTaxonomy] = None


def get_default_taxonomy() -> SkillTaxonomy:
    """Get the default skill taxonomy (singleton)."""
    global _default_taxonomy
    if _default_taxonomy is None:
        _default_taxonomy = CSBagrutTaxonomy()
    return _default_taxonomy
