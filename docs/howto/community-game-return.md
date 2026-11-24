# Back to game

When a learner follows **Visit word page** or **Visit entry** from flashcards,
a picture crossword or a word scramble, the destination has a visible,
sticky **Back to game** control. It returns directly to that activity, preserving
the card order, revealed answer, counts, selected puzzle clue and solved squares.
The return context follows subsequent links between word, sentence and picture
pages in the same dictionary. Ordinary browsing has no extra control. Member and
public practice use their respective authorized routes. All six flashcard
directions, recall and multiple choice share this mechanism.

Progress is temporary and local to the browser tab, with a two-hour expiry.
Closing the tab or choosing another activity clears it. Session storage contains
a random game seed, content revision, entry IDs, counts, solved paths and display
state, never the dictionary wording, translations, image/audio URLs or recordings.
The category is retained to return to the same selection. No AI request, charge,
learner database record, migration or new dependency is involved.

On return, the existing data endpoint rebuilds the seeded activity from the
current authorized catalogue. A changed dictionary, revoked access, missing
snapshot or expired game leads to a clear message and a fresh activity choice.
The browser's Back button also rechecks a retained game before displaying it.
Without usable session storage the return link still leads to the activity
choices, with a message explaining that the old game is unavailable.

The client checks run the actual scripts with isolated DOM stubs: recall and
multiple-choice progress, both puzzles, pagehide/browser Back, expired/malformed
and other-account snapshots, changed/withdrawn content, and repeated reading-page
navigation. Django tests cover optional controls, translations, safe return
destinations, access boundaries and deterministic reconstruction. A physical
phone/browser trial remains separate from these checks.
