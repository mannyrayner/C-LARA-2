Nearly everything works! This is another big step forward. The workflow feels enormously faster and more intuitive, and the dictionary itself feels much more useful.



We should install on AWS and test with a larger set of images, but a few things we need to fix first:



1. I am not sure where we are on handling multi-word expressions. With the image of Finley stretched out on the sofa, I used the Swedish sentence "Katten sträcker ut sig på soffan" and was offered words which included "sträcka" and "ut". Really, we want "sträcka ut sig". Are we trying to apply the C-LARA-2 MWE identification stage? If not, this is probably desirable.
2. Irrespective of whether we have MWE identification, we should allow the user to edit the list of word suggestions, modifying, adding or deleting words.
3. For testing on MWE, it would be handy to add a control in "Settings" that allows creation of a dictionary copy that contains only the image information. I think we will only need this temporarily, while we transition to the new way of doing things, then we can take it out again.



What do you think?
