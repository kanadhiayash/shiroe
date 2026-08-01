# ContradictionGuard

ContradictionGuard prevents Shiroe from silently storing conflicting active memory
cards.

It currently treats active cards with the same normalized title and different
claims as high-severity conflicts. High-severity conflicts block guarded writes
until the user resolves or supersedes the older card.

Commands:

```bash
shiroe contradictions scan memory/
shiroe contradictions list
shiroe contradictions show conflict_<id>
shiroe contradictions resolve conflict_<id> --winner mem_2026_07_09_0001 --reason "User confirmed."
shiroe contradictions archive conflict_<id>
```

Open conflicts are mirrored to `memory/CONFLICTS.md` for human arbitration.
