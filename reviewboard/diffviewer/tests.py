from itertools import izip_longest as zip_longest
import nose
from reviewboard.diffviewer.processors import (filter_interdiff_opcodes,
                                               merge_adjacent_chunks)
from reviewboard.testing import TestCase
                          ("equal", 0, 6, 2, 8)])
                         [("equal", 0, 4, 0, 4),
                          ("insert", 5, 5, 5, 9),
                          ("equal", 5, 8, 9, 12)])
            self.assertTrue(file.origFile.startswith("%s/orig_src/" %
            self.assertTrue(file.newFile.startswith("%s/new_src/" %
    def test_move_detection(self):
        """Testing diff viewer move detection"""
        self._test_move_detection(
            old.splitlines(),
            new.splitlines(),
            [
                {
                    28: 15,
                    29: 16,
                    30: 17,
                    31: 18,
                    32: 19,
                }
            ],
            [
                {
                    15: 28,
                    16: 29,
                    17: 30,
                    18: 31,
                    19: 32,
                }
            ])

    def test_move_detection_with_replace_lines(self):
        """Testing dfif viewer move detection with replace lines"""
        self._test_move_detection(
            [
                'this is line 1',
                '----------',
                '----------',
                'this is line 2',
            ],
            [
                'this is line 2',
                '----------',
                '----------',
                'this is line 1',
            ],
            [
                {1: 4},
                {4: 1},
            ],
            [
                {1: 4},
                {4: 1},
            ]
        )
    def test_move_detection_with_adjacent_regions(self):
        """Testing dfif viewer move detection with adjacent regions"""
        self._test_move_detection(
            [
                '1. Lorem ipsum dolor sit amet, consectetur adipiscing elit.',
                '2. Phasellus et lectus vulputate, dictum mi id, auctor ante.',
                '3. Nulla accumsan tellus ut felis ultrices euismod.',
                '4. Donec quis augue sed arcu tristique pellentesque.',
                '5. Fusce rutrum diam vel viverra sagittis.',
                '6. Nam tincidunt sapien vitae lorem vestibulum tempor.',
                '7. Donec fermentum tortor ut egestas convallis.',
            ],
            [
                '6. Nam tincidunt sapien vitae lorem vestibulum tempor.',
                '7. Donec fermentum tortor ut egestas convallis.',
                '4. Donec quis augue sed arcu tristique pellentesque.',
                '5. Fusce rutrum diam vel viverra sagittis.',
                '1. Lorem ipsum dolor sit amet, consectetur adipiscing elit.',
                '2. Phasellus et lectus vulputate, dictum mi id, auctor ante.',
                '3. Nulla accumsan tellus ut felis ultrices euismod.',
            ],
            [
                {
                    1: 6,
                    2: 7,
                    3: 4,
                    4: 5,
                }
            ],
            [
                {
                    4: 3,
                    5: 4,
                    6: 1,
                    7: 2,
                }
            ],
        )
    def test_line_counts(self):
        """Testing DiffParser with insert/delete line counts"""
        diff = (
            '+ This is some line before the change\n'
            '- And another line\n'
            'Index: foo\n'
            '- One last.\n'
            '--- README  123\n'
            '+++ README  (new)\n'
            '@ -1,1 +1,1 @@\n'
            '-blah blah\n'
            '-blah\n'
            '+blah!\n'
            '-blah...\n'
            '+blah?\n'
            '-blah!\n'
            '+blah?!\n')
        files = diffparser.DiffParser(diff).parse()
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].insert_count, 3)
        self.assertEqual(files[0].delete_count, 4)
    def _test_move_detection(self, a, b, expected_i_moves, expected_r_moves):
        differ = MyersDiffer(a, b)
        opcode_generator = get_diff_opcode_generator(differ)

        r_moves = []
        i_moves = []

        for opcodes in opcode_generator:
            tag = opcodes[0]
            meta = opcodes[-1]

            if 'moved-to' in meta:
                r_moves.append(meta['moved-to'])

            if 'moved-from' in meta:
                i_moves.append(meta['moved-from'])

        self.assertEqual(i_moves, expected_i_moves)
        self.assertEqual(r_moves, expected_r_moves)


class FileDiffMigrationTests(TestCase):
    fixtures = ['test_scmtools']

    def setUp(self):
        self.diff = (
            'diff --git a/README b/README\n'
            'index d6613f5..5b50866 100644\n'
            '--- README\n'
            '+++ README\n'
            '@ -1,1 +1,1 @@\n'
            '-blah blah\n'
            '+blah!\n')
        self.parent_diff = (
            'diff --git a/README b/README\n'
            'index d6613f5..5b50866 100644\n'
            '--- README\n'
            '+++ README\n'
            '@ -1,1 +1,1 @@\n'
            '-blah..\n'
            '+blah blah\n')

        repository = self.create_repository(tool_name='Test')
        diffset = DiffSet.objects.create(name='test',
                                         revision=1,
                                         repository=repository)
        self.filediff = FileDiff(source_file='README',
                                 dest_file='README',
                                 diffset=diffset,
                                 diff64='',
                                 parent_diff64='')

    def test_migration_by_diff(self):
        """Testing FileDiffData migration accessing FileDiff.diff"""
        self.filediff.diff64 = self.diff

        self.assertEqual(self.filediff.diff_hash, None)
        self.assertEqual(self.filediff.parent_diff_hash, None)

        # This should prompt the migration
        diff = self.filediff.diff

        self.assertEqual(self.filediff.parent_diff_hash, None)
        self.assertNotEqual(self.filediff.diff_hash, None)

        self.assertEqual(diff, self.diff)
        self.assertEqual(self.filediff.diff64, '')
        self.assertEqual(self.filediff.diff_hash.binary, self.diff)
        self.assertEqual(self.filediff.diff, diff)
        self.assertEqual(self.filediff.parent_diff, None)
        self.assertEqual(self.filediff.parent_diff_hash, None)

    def test_migration_by_parent_diff(self):
        """Testing FileDiffData migration accessing FileDiff.parent_diff"""
        self.filediff.diff64 = self.diff
        self.filediff.parent_diff64 = self.parent_diff

        self.assertEqual(self.filediff.parent_diff_hash, None)

        # This should prompt the migration
        parent_diff = self.filediff.parent_diff

        self.assertNotEqual(self.filediff.parent_diff_hash, None)

        self.assertEqual(parent_diff, self.parent_diff)
        self.assertEqual(self.filediff.parent_diff64, '')
        self.assertEqual(self.filediff.parent_diff_hash.binary,
                         self.parent_diff)
        self.assertEqual(self.filediff.parent_diff, self.parent_diff)

    def test_migration_by_delete_count(self):
        """Testing FileDiffData migration accessing FileDiff.delete_count"""
        self.filediff.diff64 = self.diff

        self.assertEqual(self.filediff.diff_hash, None)

        # This should prompt the migration
        delete_count = self.filediff.delete_count

        self.assertNotEqual(self.filediff.diff_hash, None)
        self.assertEqual(delete_count, 1)
        self.assertEqual(self.filediff.diff_hash.delete_count, 1)

    def test_migration_by_insert_count(self):
        """Testing FileDiffData migration accessing FileDiff.insert_count"""
        self.filediff.diff64 = self.diff

        self.assertEqual(self.filediff.diff_hash, None)

        # This should prompt the migration
        insert_count = self.filediff.insert_count

        self.assertNotEqual(self.filediff.diff_hash, None)
        self.assertEqual(insert_count, 1)
        self.assertEqual(self.filediff.diff_hash.insert_count, 1)

    def test_migration_by_set_line_counts(self):
        """Testing FileDiffData migration calling FileDiff.set_line_counts"""
        self.filediff.diff64 = self.diff

        self.assertEqual(self.filediff.diff_hash, None)

        # This should prompt the migration, but with our line counts.
        self.filediff.set_line_counts(10, 20)

        self.assertNotEqual(self.filediff.diff_hash, None)
        self.assertEqual(self.filediff.insert_count, 10)
        self.assertEqual(self.filediff.delete_count, 20)
        self.assertEqual(self.filediff.diff_hash.insert_count, 10)
        self.assertEqual(self.filediff.diff_hash.delete_count, 20)

                          '<span class="hl">abc</span>')
                          '<span class="hl">a</span>bc')
        repository = self.create_repository()
        repository = self.create_repository()
            'diff --git a/README b/README\n'
            'index d6613f5..5b50866 100644\n'
            '--- README\n'
            '+++ README\n'
        repository = self.create_repository(tool_name='Test')
            'diff --git a/README b/README\n'
            'index d6613f5..5b50866 100644\n'
            '--- README\n'
            '+++ README\n'
        repository = self.create_repository(tool_name='Test')
            'diff --git a/README b/README\n'
            'index d6613f5..5b50866 100644\n'
            '--- README\n'
            '+++ README\n'
            'diff --git a/README b/README\n'
            'index d6613f4..5b50865 100644\n'
            '--- README\n'
            '+++ README\n'
            'diff --git a/UNUSED b/UNUSED\n'
            'index 1234567..5b50866 100644\n'
            '--- UNUSED\n'
            '+++ UNUSED\n'
        repository = self.create_repository(tool_name='Test')
        self.assertTrue(('/README', 'd6613f4') in saw_file_exists)
        self.assertFalse(('/UNUSED', '1234567') in saw_file_exists)
        try:
            import mercurial
        except ImportError:
            raise nose.SkipTest("Hg is not installed")

class ProcessorsTests(TestCase):
    """Unit tests for diff processors."""

    def test_filter_interdiff_opcodes(self):
        """Testing filter_interdiff_opcodes"""
        opcodes = [
            ('insert', 0, 0, 0, 1),
            ('equal', 0, 5, 1, 5),
            ('delete', 5, 10, 5, 5),
            ('equal', 10, 25, 5, 20),
            ('replace', 25, 26, 20, 26),
            ('equal', 26, 40, 26, 40),
            ('insert', 40, 40, 40, 45),
        ]

        # NOTE: Only the "@@" lines in the diff matter below for this
        #       processor, so the rest can be left out.
        orig_diff = '@@ -22,7 +22,7 @@\n'
        new_diff = (
            '@@ -2,11 +2,6 @@\n'
            '@@ -22,7 +22,7 @@\n'
        )

        new_opcodes = list(filter_interdiff_opcodes(opcodes, orig_diff,
                                                    new_diff))

        self.assertEqual(new_opcodes, [
            ('equal', 0, 0, 0, 1),
            ('equal', 0, 5, 1, 5),
            ('delete', 5, 10, 5, 5),
            ('equal', 10, 25, 5, 20),
            ('replace', 25, 26, 20, 26),
            ('equal', 26, 40, 26, 40),
            ('equal', 40, 40, 40, 45),
        ])

    def test_filter_interdiff_opcodes_with_inserts_right(self):
        """Testing filter_interdiff_opcodes with inserts on the right"""
        # These opcodes were taken from the r1-r2 interdiff at
        # http://reviews.reviewboard.org/r/4221/
        opcodes = [
            ('equal', 0, 141, 0, 141),
            ('replace', 141, 142, 141, 142),
            ('insert', 142, 142, 142, 144),
            ('equal', 142, 165, 144, 167),
            ('replace', 165, 166, 167, 168),
            ('insert', 166, 166, 168, 170),
            ('equal', 166, 190, 170, 194),
            ('insert', 190, 190, 194, 197),
            ('equal', 190, 232, 197, 239),
        ]

        # NOTE: Only the "@@" lines in the diff matter below for this
        #       processor, so the rest can be left out.
        orig_diff = '@@ -0,0 +1,232 @@\n'
        new_diff = '@@ -0,0 +1,239 @@\n'

        new_opcodes = list(filter_interdiff_opcodes(opcodes, orig_diff,
                                                    new_diff))

        self.assertEqual(new_opcodes, [
            ('equal', 0, 141, 0, 141),
            ('replace', 141, 142, 141, 142),
            ('insert', 142, 142, 142, 144),
            ('equal', 142, 165, 144, 167),
            ('replace', 165, 166, 167, 168),
            ('insert', 166, 166, 168, 170),
            ('equal', 166, 190, 170, 194),
            ('insert', 190, 190, 194, 197),
            ('equal', 190, 232, 197, 239),
        ])

    def test_filter_interdiff_opcodes_with_many_ignorable_ranges(self):
        """Testing filter_interdiff_opcodes with many ignorable ranges"""
        # These opcodes were taken from the r1-r2 interdiff at
        # http://reviews.reviewboard.org/r/4257/
        opcodes = [
            ('equal', 0, 631, 0, 631),
            ('replace', 631, 632, 631, 632),
            ('insert', 632, 632, 632, 633),
            ('equal', 632, 882, 633, 883),
        ]

        # NOTE: Only the "@@" lines in the diff matter below for this
        #       processor, so the rest can be left out.
        orig_diff = (
            '@@ -413,6 +413,8 @@\n'
            '@@ -422,9 +424,13 @@\n'
            '@@ -433,6 +439,8 @@\n'
            '@@ -442,6 +450,9 @@\n'
            '@@ -595,6 +605,205 @@\n'
            '@@ -636,6 +845,36 @@\n'
        )
        new_diff = (
            '@@ -413,6 +413,8 @@\n'
            '@@ -422,9 +424,13 @@\n'
            '@@ -433,6 +439,8 @@\n'
            '@@ -442,6 +450,8 @@\n'
            '@@ -595,6 +605,206 @@\n'
            '@@ -636,6 +846,36 @@\n'
        )

        new_opcodes = list(filter_interdiff_opcodes(opcodes, orig_diff,
                                                    new_diff))

        self.assertEqual(new_opcodes, [
            ('equal', 0, 631, 0, 631),
            ('replace', 631, 632, 631, 632),
            ('insert', 632, 632, 632, 633),
            ('equal', 632, 882, 633, 883),
        ])

    def test_merge_adjacent_chunks(self):
        """Testing merge_adjacent_chunks"""
        opcodes = [
            ('equal', 0, 0, 0, 1),
            ('equal', 0, 5, 1, 5),
            ('delete', 5, 10, 5, 5),
            ('equal', 10, 25, 5, 20),
            ('replace', 25, 26, 20, 26),
            ('equal', 26, 40, 26, 40),
            ('equal', 40, 40, 40, 45),
        ]

        new_opcodes = list(merge_adjacent_chunks(opcodes))

        self.assertEqual(new_opcodes, [
            ('equal', 0, 5, 0, 5),
            ('delete', 5, 10, 5, 5),
            ('equal', 10, 25, 5, 20),
            ('replace', 25, 26, 20, 26),
            ('equal', 26, 40, 26, 45),
        ])


                for a, b in zip_longest(A, B):
            'newfile': True,
            'interfilediff': None,
            'filediff': FileDiff(),