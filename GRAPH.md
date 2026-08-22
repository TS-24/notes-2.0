# The note graph

Deferred on purpose. This file is the branch's whole contents: it says what the
feature is, what has already been paid for, and what must not be assumed.

## What already exists

`notes.parent_id` — a nullable, indexed, self-referential foreign key on
`notes`, added in migration `e7d41a20c9b8` (PR #51, on `feat/note-chat-binding`;
not on `dev` until that merges). **Nothing reads it.**

It is there because adding a self-reference to a table this central is the
expensive half of this work: it is a migration against live data, and doing it
under a feature that also has to ship a UI means two risky things landing in one
release. It now costs one nullable column and nothing else.

`chats.note_id` is the other relationship in the schema, and it is *not* this
one. It is one-to-one and it binds a conversation to the note it is two faces
of. A note's parent is a different kind of edge and must not be folded into it.

## What the feature is

Notes relate to other notes, and the library can be read as that shape rather
than as a grid ordered by when things were touched.

Two questions it exists to answer, which the grid cannot:

- What came out of this? A conversation about tides produces a note; writing in
  that note produces another conversation and another note. Today that lineage
  is a timestamp ordering and nothing else.
- What is this part of? A note written three weeks ago is unreachable unless you
  remember its title.

## Open questions, before any code

1. **Is one parent enough?** `parent_id` is a tree. A genuine graph needs an
   edge table. A tree is cheaper, renders trivially, and is probably what the
   note-to-conversation-to-note lineage actually is — but it cannot express "these
   two notes are about the same thing", which is the other half of why anyone
   wants a graph. Decide this before building either.
2. **Is the parent set by hand or inferred?** Finishing a conversation started
   from note A writes into note A, so nothing new is created and no edge is
   implied. A second conversation started *from* the note that a first one wrote
   is where lineage actually appears. Whether that edge is written automatically
   is a product decision, not a schema one.
3. **What does the view replace?** DESIGN.md §9 rule 8 says while you are in a
   note, the note is the only thing on screen. A graph view is a second way to
   read the library, not a panel beside the first.
4. **How does it stay fast?** The workspace loader deliberately does not
   revalidate on navigation (PROGRESS.md trap 35). A graph that refetches on
   every pan undoes that. The edges are small; they belong in the loader that is
   already running.

## What not to do

- Do not backfill `parent_id` from timestamps or title similarity. A guessed
  edge is worse than no edge: it is unfalsifiable to the reader and it will be
  believed.
- Do not add a graph library before question 1 is settled. The answer decides
  whether this is a tree render or a force layout, and those share nothing.
