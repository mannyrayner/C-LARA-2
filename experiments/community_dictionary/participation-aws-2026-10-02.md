# AWS participation deployment and trial — 2 October 2026

## Result and evidence limits

Manny reports successful deployment and use of dictionary-wide withdrawal and
restoration on AWS. After service recovery he could access Community Dictionaries,
saw the new controls and found normal behaviour while browsing. Following the
suggested withdrawal/restoration sequence, he reported that everything worked as
intended. He plans to notify Kate, Axel and Sophie that the service is available
again and ask Sophie about the model's suitability for her community.

This is human-reported server acceptance. The report does not enumerate accounts,
dictionary IDs, individual assertions or a new physical-phone trial. Earlier
laptop acceptance explicitly included ownership handover. The controlled suite
remains 156 tests; no new runtime code or automated test result accompanies this
documentation update. New server code/migration state is evidenced by the supplied
trace, but its deployed Git SHA was not supplied in this exchange.

## Backup and deployment evidence

- AWS initially had Community Dictionaries migrations 0001–0005 applied.
- The first dump attempt failed because PostgreSQL server 18.3 was accessed with
  `pg_dump` 16.15. Manny installed the version 18 client tools; both `pg_dump` and
  `pg_restore` subsequently reported 18.6. Explicit versioned binary paths were used.
- A silent compressed-media backup was interrupted with Ctrl+C while the Python
  block was waiting for an archive verification subprocess. The original site was
  restarted and Manny confirmed that it worked. The interrupted files were retained
  as unverified; they were not treated as a completed recovery point.
- Before the second attempt, no tar/gzip/pg_dump processes remained. The filesystem
  reported 48 GB available; public media occupied 22 GB, private dictionary media
  23 MB, and earlier backups 5.1 GB. Manny notified the three known testers of a
  maintenance window. Both applications share the services and the downtime.
- A fresh database dump and uncompressed media archives were made with writers
  stopped. Media creation and comparison printed progress checkpoints. Both public
  and private media comparisons passed. The reported backup directory was
  `/home/ssm-user/clara2-backups/evening-20261002-091819`.
- The database dump was checked by listing its archive. This and media comparison
  are backup checks, not a full database/media restore rehearsal.
- Migrations 0006, 0007 and 0008 applied successfully. The audit reported zero
  private contributions and zero private entries, permitting the one-time reset.
  Migration 0009 then applied successfully; Django check passed and collectstatic
  completed (with a duplicate favicon warning).

## Service-start incident and recovery

All three services failed on the first start, although shell management commands
worked as `ssm-user`. The backup runbook had set `umask 077` in the interactive
shell and failed to restore it before Git/pip operations. A local reproduction
confirmed that Git checkout under that mask creates changed files with mode 0600
and new directories with mode 0700. The services run as a different user, `ubuntu`.

Manny reset the shell mask to 022, restored read/traversal permissions on the
Community Dictionaries source directory, reset failed service states and restarted
the services. He then reported that all processes ran normally and the application
worked. This strongly supports the permission diagnosis; a service exception
trace was not supplied before the successful repair. No database rollback was used.

The [deployment guide](../../docs/howto/community-participation-aws.md) now keeps
the restrictive backup mask in a subshell/Python process, explicitly sets 022
before code/dependency/static deployment, uses PostgreSQL 18 clients, prints backup
progress, and includes the narrowly scoped permission recovery. Private media and
backups must not receive the source-code permission repair.

## Implications and next step

The simpler participation model now has laptop and AWS acceptance evidence. Sophie
has not yet assessed this final workflow with community members. That remains a
user question, alongside wording, ownership handover expectations and phone use.

The deployment also required substantial human work and exposed defects in the
assistant's instructions. It is evidence for improving operational automation and
runbook quality, not evidence of autonomous maintenance. Priorities are to retain
these corrections, collect stakeholder feedback and avoid changing the established
interaction model without a concrete need. Backup retention/cleanup can be planned
after acceptance; no old archives were deleted by this update.
