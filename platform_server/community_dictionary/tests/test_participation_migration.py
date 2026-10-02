import io
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection, migrations
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class ParticipationMigrationTests(TransactionTestCase):
    def setUp(self):
        from community_dictionary.models import Contribution
        self.assertFalse(Contribution.objects.exists())
        executor = MigrationExecutor(connection)
        # Preparing an old-schema fixture in an empty disposable database only.
        executor.loader.get_migration('community_dictionary', '0009_restore_experimental_collections').operations[0].reverse_code = migrations.RunPython.noop
        executor.migrate([('community_dictionary', '0007_split_text_provenance')])
        self.apps = executor.loader.project_state([('community_dictionary', '0007_split_text_provenance')]).apps
        User = self.apps.get_model('auth', 'User')
        self.owner = User.objects.create(username='migration_owner')
        self.member = User.objects.create(username='migration_member')
        D = self.apps.get_model('community_dictionary', 'Dictionary')
        E = self.apps.get_model('community_dictionary', 'Entry')
        self.source = D.objects.create(owner_id=self.owner.pk, name='Swedish', language='Swedish')
        self.entry = E.objects.create(dictionary=self.source, created_by_id=self.member.pk)
        self.private = D.objects.create(owner_id=self.member.pk, name='Private', language='Swedish', personal=True, collection_source=self.source)
        self.retained = E.objects.create(dictionary=self.private, created_by_id=self.member.pk, collection_source=self.entry)
        self.Part = self.apps.get_model('community_dictionary', 'Contribution')

    def migrate(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def tearDown(self):
        self.migrate()
        super().tearDown()

    def part(self, **kwargs):
        return self.Part.objects.create(entry=self.retained, author_id=self.member.pk,
            controlled_by_id=self.member.pk, status='accepted', withdrawn_from=self.entry,
            provenance={'status_before_withdrawal':'accepted'}, **kwargs)

    def test_originals_and_pending_returned_copies_merge_without_losing_provenance(self):
        original=self.part(kind='image',file_path='fixture/photo.jpg',mime_type='image/jpeg')
        copy=self.Part.objects.create(entry=self.entry,author_id=self.member.pk,controlled_by_id=self.member.pk,
            status='pending',kind='image',file_path=original.file_path,mime_type=original.mime_type,shared_from=original)
        self.migrate()
        from community_dictionary.models import Contribution, Entry, Participation
        original=Contribution.objects.get(pk=original.pk);copy=Contribution.objects.get(pk=copy.pk)
        self.assertEqual((original.entry_id,copy.entry_id),(self.entry.pk,self.entry.pk))
        self.assertEqual((original.status,copy.status),('superseded','accepted'))
        self.assertEqual(copy.shared_from_id,original.pk)
        self.assertEqual(copy.controlled_by_id,self.member.pk)
        self.assertEqual(Entry.objects.get(pk=self.entry.pk).selected_image_id,copy.pk)
        self.assertFalse(Contribution.objects.filter(entry__dictionary__personal=True).exists())
        self.assertFalse(Participation.objects.filter(withdrawn=True).exists())

    def test_newer_shared_text_keeps_credit_and_private_history_returns(self):
        old=self.part(kind='text',text_field='meaning',meaning='sofa')
        current=self.Part.objects.create(entry=self.entry,author_id=self.owner.pk,controlled_by_id=self.owner.pk,
            kind='text',text_field='meaning',meaning='couch',status='accepted')
        self.entry.meaning='couch';self.entry.current_meaning_id=current.pk;self.entry.meaning_version=7;self.entry.save()
        self.migrate()
        from community_dictionary.models import Contribution, Entry
        entry=Entry.objects.get(pk=self.entry.pk);old=Contribution.objects.get(pk=old.pk)
        self.assertEqual((entry.meaning,entry.current_meaning_id,entry.meaning_version),('couch',current.pk,7))
        self.assertEqual(old.entry_id,entry.pk);self.assertEqual(old.controlled_by_id,self.member.pk)
        self.assertEqual(old.status,'accepted')

    def test_private_additions_get_one_original_entry_and_need_review(self):
        E=self.apps.get_model('community_dictionary','Entry')
        extra=E.objects.create(dictionary=self.private,created_by_id=self.member.pk)
        ids=[]
        for value in ['First private note','Second private note']:
            p=self.Part.objects.create(entry=extra,author_id=self.member.pk,controlled_by_id=self.member.pk,
                kind='note',body=value,status='accepted')
            ids.append(p.pk)
        self.migrate()
        from community_dictionary.models import Contribution
        rows=list(Contribution.objects.filter(pk__in=ids))
        self.assertEqual(len({p.entry_id for p in rows}),1)
        self.assertTrue(all(p.entry.dictionary_id==self.source.pk and p.status=='pending' for p in rows))

    def test_preflight_works_before_schema_upgrade_and_empty_server_has_no_content_changes(self):
        ordinary=self.Part.objects.create(entry=self.entry,author_id=self.owner.pk,controlled_by_id=self.owner.pk,
            kind='text',text_field='word',word='hej',status='accepted')
        before=list(self.Part.objects.values())
        output=io.StringIO();call_command('community_withdrawal_audit',expect_empty=True,stdout=output)
        self.assertIn('Private contributions: 0',output.getvalue())
        self.migrate()
        from community_dictionary.models import Contribution, Participation
        self.assertEqual(list(Contribution.objects.values()),before)
        self.assertFalse(Participation.objects.exists())

    def test_preflight_stops_nonempty_aws_assumption_without_modifying_data(self):
        part=self.part(kind='image')
        with self.assertRaises(CommandError):
            call_command('community_withdrawal_audit',expect_empty=True,stdout=io.StringIO())
        self.assertEqual(self.Part.objects.get(pk=part.pk).entry_id,self.retained.pk)
