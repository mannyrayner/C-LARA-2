from django.db import connection, migrations
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class ProvenanceMigrationTests(TransactionTestCase):
    def test_surviving_translation_credit_is_recovered_without_guessing_deleted_history(self):
        from community_dictionary.models import Entry as LiveEntry
        self.assertFalse(LiveEntry.objects.exists())
        executor = MigrationExecutor(connection)
        # This disposable database is empty. Only for preparing the old-schema
        # fixture, reversing the data-only operation is therefore a no-op.
        executor.loader.get_migration('community_dictionary', '0007_split_text_provenance').operations[0].reverse_code = migrations.RunPython.noop
        executor.loader.get_migration('community_dictionary', '0009_restore_experimental_collections').operations[0].reverse_code = migrations.RunPython.noop
        executor.migrate([('community_dictionary', '0005_image_word_links')])
        old = executor.loader.project_state([('community_dictionary', '0005_image_word_links')]).apps
        User = old.get_model('auth', 'User')
        cathy = User.objects.create(username='migration_cathy')
        manny = User.objects.create(username='migration_manny')
        Dictionary = old.get_model('community_dictionary', 'Dictionary')
        Entry = old.get_model('community_dictionary', 'Entry')
        Part = old.get_model('community_dictionary', 'Contribution')
        Membership = old.get_model('community_dictionary', 'Membership')
        d = Dictionary.objects.create(owner_id=manny.pk, name='Migration trial', language='Swedish')
        Membership.objects.create(dictionary=d, user_id=cathy.pk, accepted=True)
        e = Entry.objects.create(dictionary=d, created_by_id=cathy.pk)
        first = Part.objects.create(entry=e, author_id=cathy.pk, kind='text', status='accepted', meaning='sofa', base_version=0)
        second = Part.objects.create(entry=e, author_id=manny.pk, kind='text', status='accepted', word='soffa', meaning='sofa', category='Home', base_version=1)
        e.word, e.meaning, e.category, e.text_version, e.current_text_id = 'soffa', 'sofa', 'Home', 2, second.pk
        e.save()
        lost = Entry.objects.create(dictionary=d, created_by_id=cathy.pk, word='katt', meaning='cat', text_version=5)
        surviving = Part.objects.create(entry=lost, author_id=manny.pk, kind='text', status='accepted', word='katt', meaning='cat', base_version=4)
        lost.current_text_id = surviving.pk; lost.save()
        proposal = Part.objects.create(entry=e, author_id=cathy.pk, kind='text', status='withdrawn', word='private', meaning='secret', base_version=2)
        audio = Part.objects.create(entry=e, author_id=manny.pk, kind='audio', status='accepted', provenance={'origin': 'synthetic', 'source_text_id': second.pk, 'source_text': 'soffa', 'source_text_version': 2, 'language': 'Swedish'})
        try:
            executor = MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())
            from community_dictionary.models import Entry as NewEntry, Membership as NewMembership, Contribution
            updated = NewEntry.objects.get(pk=e.pk)
            self.assertEqual((updated.word, updated.meaning, updated.category), ('soffa', 'sofa', 'Home'))
            self.assertEqual(updated.current_meaning.controlled_by_id, cathy.pk)
            self.assertEqual(updated.current_text.controlled_by_id, manny.pk)
            self.assertEqual(updated.current_category.controlled_by_id, manny.pk)
            self.assertEqual(updated.text_version, 2)
            self.assertEqual(NewMembership.objects.get(dictionary_id=d.pk).status, 'active')
            self.assertEqual(NewEntry.objects.get(pk=lost.pk).current_meaning.controlled_by_id, manny.pk)
            self.assertEqual(Contribution.objects.get(pk=audio.pk).shared_from_id, updated.current_text_id)
            retained = Contribution.objects.get(pk=proposal.pk)
            self.assertEqual(retained.entry_id, updated.pk)
            self.assertEqual(retained.controlled_by_id, cathy.pk)
            self.assertEqual(retained.status, 'pending')
            self.assertEqual(updated.word, 'soffa')
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())
