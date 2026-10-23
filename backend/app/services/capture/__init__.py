"""
In-house scanning — the capture service (PR_in_house_scanning.md §6).

One service used by both modes (the student link and the teacher page); the
routers are thin auth adapters that resolve a `CaptureActor` and call in here.
"""
