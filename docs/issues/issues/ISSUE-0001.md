# ISSUE-0001: Support hosted compiled legacy content registration in C-LARA-2

- **Status:** reported
- **Priority:** P2
- **Created:** 2026-05-03T08:13:34Z
- **Updated:** 2026-05-11T09:17:04Z
- **Origin:** human-suggestion
- **Deadline:** None
- **Dependencies:** None
- **Canonical JSON:** [ISSUE-0001.json](ISSUE-0001.json)

## Notes

Suggestion #1 from admin export (submitted by mannyrayner on 2026-05-03). Add a mechanism similar to
legacy C-LARA where precompiled external or server-hosted content can be registered as C-LARA-2
content via metadata fields (at minimum: content URL, text language, glossing language, publication
date). Clarify security and ownership constraints for off-server URLs. Follow-up operational note
from 2026-05-11: the first implementation/evaluation pass should start by copying the large folder
of compiled legacy LARA material from the laptop to AWS using the same SSH/rsync pattern that worked
for the Adelaide C-LARA upload. The laptop source folder is `/home/LARALegacyFromServer/`. Because
this material is compiled/hosted legacy LARA content rather than importable C-LARA JSON source
bundles, keep it in a sister server directory rather than inside the Adelaide bundle library;
recommended target: `/srv/c-lara/legacy-compiled/lara/`, alongside
`/srv/c-lara/legacy-bundles/adelaide/` under `/srv/c-lara/`. A candidate transfer command is: `rsync
-avh --progress --partial --append-verify -e "ssh -i /home/CLARA2/EC2KeyPairForClara2.pem"
/home/LARALegacyFromServer/ ubuntu@c-lara-2.c-lara.org:/srv/c-lara/legacy-compiled/lara/`. Before
transfer, ensure the EC2 inbound SSH/security rule allows TCP port 22 from the uploader's current IP
address and that the `.pem` file has restrictive permissions, e.g. `chmod 600
/home/CLARA2/EC2KeyPairForClara2.pem`. After transfer, verify the server directory layout and then
design the registration metadata/import UI around stable hosted URLs, ownership/security rules,
language metadata, and publication dates.
