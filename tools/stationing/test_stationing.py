"""python -m unittest discover -s tools/stationing"""
import json
import math
import os
import tempfile
import unittest

import stationing as st


def cl_line(x0, x1, y, labels):
    ents = [{'type': 'LINE', 'start': {'x': x0, 'y': y}, 'end': {'x': x1, 'y': y}}]
    for x, text in labels:
        ents.append({'type': 'INSERT', 'blockName': 'AeccTickLine', 'position': {'x': x, 'y': y}})
        ents.append({'type': 'MTEXT', 'text': text, 'location': {'x': x, 'y': y + 4}})
    return ents


class StationingTest(unittest.TestCase):
    def test_fmt_rounds_to_nearest_foot_half_up(self):
        self.assertEqual(st.fmt(2009.4827), '20+09')
        self.assertEqual(st.fmt(2009.5), '20+10')
        self.assertEqual(st.fmt(48000.0), '480+00')
        self.assertEqual(st.fmt(1199.6), '12+00')

    def test_rect_hits_poly(self):
        sq = [(0, 0), (10, 0), (10, 10), (0, 10)]
        self.assertTrue(st.rect_hits_poly([(5, 5), (15, 5), (15, 6), (5, 6)], sq))       # crosses an edge
        self.assertTrue(st.rect_hits_poly([(2, 2), (3, 2), (3, 3), (2, 3)], sq))         # inside
        self.assertFalse(st.rect_hits_poly([(11, 11), (12, 11), (12, 12), (11, 12)], sq))

    def test_centerline_fit_gives_station_from_labels(self):
        cl = st.Centerlines(cl_line(0, 300, 0, [(50, '20+00'), (150, '21+00')]))
        self.assertEqual(len(cl.fit), 1)
        (ci, (k, a, _)), = cl.fit.items()
        d, s, _, _ = cl.project(cl.chains[ci], (59.48, 14.6))
        self.assertAlmostEqual(d, 14.6, places=2)
        self.assertEqual(st.fmt(a + k * s), '20+09')

    def test_centerline_fit_handles_decreasing_stations(self):
        cl = st.Centerlines(cl_line(0, 300, 0, [(50, '21+00'), (150, '20+00')]))
        (ci, (k, a, _)), = cl.fit.items()
        self.assertEqual(k, -1)
        _, s, _, _ = cl.project(cl.chains[ci], (140.0, -10))
        self.assertEqual(st.fmt(a + k * s), '20+10')

    def test_text_rects_sit_past_the_shelf_start(self):
        rects = st.text_rects((0, 0), 0.0, False, 13, 13, ['20+09', 'EX. SL'])
        self.assertTrue(math.isclose(min(p[0] for p in rects[0]), 6 + 13 + 13 + st.XOFF))
        self.assertGreater(max(p[1] for p in rects[0]), 0)      # LINE_1 above the shelf
        self.assertLess(min(p[1] for p in rects[1]), 0)         # LINE_2 below it

    def test_points_parser_reads_raw_tool_output(self):
        data = '6,6055162.745,2261792.42,0,PP 1044317E PER FIM\r\n7,6055341.849,2261790.414,0,SL NT\r\n'
        body = ('[Resource link: Civil 3D export result] civil3d://reports/x (retained)'
                '{"action":"export","result":{"format":"pnezd","data":%s}}' % json.dumps(data))
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, 'points.txt'), 'w', encoding='utf-8') as f:
                json.dump([{'type': 'text', 'text': body}], f)
            pts = st.Job._points(d)
        self.assertEqual([p['d'] for p in pts], ['PP 1044317E PER FIM', 'SL NT'])


if __name__ == '__main__':
    unittest.main()
