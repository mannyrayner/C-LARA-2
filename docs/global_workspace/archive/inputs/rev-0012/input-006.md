This all looks good, here is the trace:

manny@DESKTOP-0NL6MH2 /home/github/c-lara-2
$ git switch -c feature/community-dictionary-prototype

git apply --check ../community_dictionary_bootstrap.patch &&
git apply ../community_dictionary_bootstrap.patch

git add platform_server/community_dictionary \
  docs/roadmap/community-dictionary.md \
  docs/howto/community-dictionary.md \
  experiments/community_dictionary

git diff --cached --check
git diff --cached --stat
Switched to a new branch 'feature/community-dictionary-prototype'
 docs/howto/community-dictionary.md                     |  79 +++++++++
 docs/roadmap/community-dictionary.md                   | 204 ++++++++++++++++++++++
 experiments/community_dictionary/README.md             |  43 +++++
 platform_server/community_dictionary/README.md         |  20 +++
 platform_server/community_dictionary/__init__.py       |   1 +
 platform_server/community_dictionary/apps.py           |   7 +
 .../community_dictionary/migrations/__init__.py        |   1 +
 .../static/community_dictionary/.gitkeep               |   0
 .../templates/community_dictionary/.gitkeep            |   0
 platform_server/community_dictionary/tests/__init__.py |   1 +
 10 files changed, 356 insertions(+)

manny@DESKTOP-0NL6MH2 /home/github/c-lara-2
$ git commit -m "Bootstrap community dictionary app and specification"
git push -u origin feature/community-dictionary-prototype
git rev-parse HEAD
[feature/community-dictionary-prototype bc21188] Bootstrap community dictionary app and specification
 10 files changed, 356 insertions(+)
 create mode 100644 docs/howto/community-dictionary.md
 create mode 100644 docs/roadmap/community-dictionary.md
 create mode 100644 experiments/community_dictionary/README.md
 create mode 100644 platform_server/community_dictionary/README.md
 create mode 100644 platform_server/community_dictionary/__init__.py
 create mode 100644 platform_server/community_dictionary/apps.py
 create mode 100644 platform_server/community_dictionary/migrations/__init__.py
 create mode 100644 platform_server/community_dictionary/static/community_dictionary/.gitkeep
 create mode 100644 platform_server/community_dictionary/templates/community_dictionary/.gitkeep
 create mode 100644 platform_server/community_dictionary/tests/__init__.py
Username for 'https://github.com': mannyrayner
Password for 'https://mannyrayner@github.com':
Enumerating objects: 28, done.
Counting objects: 100% (28/28), done.
Delta compression using up to 12 threads
Compressing objects: 100% (16/16), done.
Writing objects: 100% (22/22), 15.75 KiB | 768.00 KiB/s, done.
Total 22 (delta 4), reused 2 (delta 0), pack-reused 0 (from 0)
remote: Resolving deltas: 100% (4/4), completed with 4 local objects.
remote:
remote: Create a pull request for 'feature/community-dictionary-prototype' on GitHub by visiting:
remote:      https://github.com/mannyrayner/C-LARA-2/pull/new/feature/community-dictionary-prototype
remote:
To https://github.com/mannyrayner/C-LARA-2
 * [new branch]      feature/community-dictionary-prototype -> feature/community-dictionary-prototype
branch 'feature/community-dictionary-prototype' set up to track 'origin/feature/community-dictionary-prototype'.
bc21188595bae9f2ee89c080243a76fdd4a960b1
