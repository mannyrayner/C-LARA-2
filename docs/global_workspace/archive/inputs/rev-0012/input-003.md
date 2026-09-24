This is progressing very well! A couple of thoughts:

1. I'm wondering if it's a good idea to put the code in the C-LARA-2 repo. One advantage is that it would simplify initial deployment, since we could just check out the code on the existing server and access it there. It's also likely that there are some pieces of C-LARA-2 functionality we'll want to reuse. Long-term, it may cause problems, but if it looks like things are diverging too much we can probably move everything quickly to a new repo.
2. If we want to include AI options for languages that are AI-supported, the ones that looked most useful to me were TTS and image generation. We could easily carry these over from C-LARA-2.
3. We probably shouldn't include these in the first prototype, though, since they won't be feasible in the Indigenous languages that are one of our main priorities. It's very important to make it easy to use voice recording and phone camera as primary modalities.
4. It may often be the case in practice that two or more people act as a de facto partnership, with some providing images and some providing audio. It may be useful to have a simple way to register such a partnership, so that partners can easily retrieve outstanding requests.

What do you think?
