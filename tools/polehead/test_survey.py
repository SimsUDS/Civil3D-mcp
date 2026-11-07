"""python -m unittest discover -s tools/polehead"""
import os
import tempfile
import unittest

import pymupdf

import survey


def _pdf(path, pages):
    doc = pymupdf.open()
    for lines in pages:
        pg = doc.new_page(width=1224, height=792)
        y = 60
        for ln in lines:
            pg.insert_text((60, y), ln, fontsize=9)
            y += 14
    doc.save(path)


class FindTest(unittest.TestCase):
    def test_classifies_every_pdf_in_the_folder(self):
        with tempfile.TemporaryDirectory() as d:
            _pdf(os.path.join(d, 'TD1_BASEMAP.pdf'), [
                ['UNDERGROUND SERVICE ALERT'],
                ['1281755E', "IN: 2/C 1/0ATW 16KV @ 36'6\"", "COM @ 22'", "IN: 3/8 DG @ 36'", 'LOOKING N', 'SOIL B']])
            _pdf(os.path.join(d, 'TD1_POLEHEADS.pdf'), [['POLE HEAD DETAIL', 'PREMADE BLOCKS']])
            out = os.path.join(d, 'out')
            self.assertEqual(survey.find(d, out), 0)
            import json
            rep = json.load(open(os.path.join(out, 'find.json'), encoding='utf-8'))
            kinds = {(r['pdf'], r['page']): r['kind'] for r in rep}
            self.assertEqual(kinds[('TD1_BASEMAP.pdf', 1)], 'other')
            self.assertEqual(kinds[('TD1_BASEMAP.pdf', 2)], 'sketch')
            self.assertEqual(kinds[('TD1_POLEHEADS.pdf', 1)], 'blank')
            sk = next(r for r in rep if r['kind'] == 'sketch')
            self.assertEqual(sk['looking'][0]['dir'], 'N')
            self.assertIn('1281755E', sk['poles'])
            self.assertTrue(os.path.exists(os.path.join(out, sk['thumb'])))


if __name__ == '__main__':
    unittest.main()
