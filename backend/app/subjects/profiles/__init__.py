"""One PACKAGE per subject ([Q-18], grader-v6 Phase 2). Each exports the same names:

    KEY, MODALITIES, EXTRACTION_FRAGMENT, P1_FRAGMENT, VERIFY_FRAGMENT, P2_KEYWORDS
        — the multisubject seam, in the package's __init__.py, unchanged.
    PACK_ID, PACK_VERSION, PLANNER_FRAGMENT, VERIFIER_FRAGMENT, EXPLAINER_FRAGMENT, PRECEDENTS
        — the v6 subject pack (PR_grader_v6_options.md §8): planner.py, verifier.py,
          explainer.py and precedents.py, re-exported by __init__.py.

Seam fragments are the ONLY new prompt text of the multisubject beta (execution plan section 4.1):
<= 12 lines each, no pedagogy, no example longer than one line. They are written blind -
no eval exists behind any non-CS fragment - so less text is less unmeasured risk. The same
discipline holds for the non-CS pack fragments.

`registry.get_profile` is the ONLY lookup; nothing imports a pack by path to read a fragment.
A new subject is a new package here (plus its ontology entry) and nothing else.
"""
