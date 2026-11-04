"""python -m unittest discover -s tools/polehead"""
import json
import os
import unittest

import polehead as ph
import station_builder as sbm

HERE = os.path.dirname(os.path.abspath(__file__))


def example():
    with open(os.path.join(HERE, 'examples', 'TD2536120.json'), encoding='utf-8') as f:
        return json.load(f)


class GeneratorTests(unittest.TestCase):
    def setUp(self):
        self.J = ph.build_job(example())
        self.job = self.J.to_apply_job()

    def test_every_ref_points_at_a_copied_handle(self):
        copies = {c['id']: set(c['handles']) for c in self.job['copies']}
        for e in self.job['edits']:
            if 'ref' in e:
                cid, h = e['ref'].split(':')
                self.assertIn(h, copies[cid], e['ref'])

    def test_grouped_copies_never_repeat_a_handle(self):
        for c in self.job['copies']:
            self.assertEqual(len(c['handles']), len(set(c['handles'])))

    def test_span_guys_use_the_halves(self):
        sg = [c for c in self.job['copies'] if '2E3466' in c['handles'] or '2E3954' in c['handles']]
        self.assertTrue(sg)
        self.assertFalse(any('mirrorX' in c for c in sg))
        guy_edits = [e for e in self.job['edits'] if e.get('ref', '').endswith(':2E3B8F')]
        for e in guy_edits:                               # every GUY copy is a down guy to ground
            self.assertEqual(len(e['vertices']), 2)

    def test_dim_labels_do_not_overlap(self):
        dims = [e for e in self.job['edits'] if 'xLine2' in e and 'textPosition' in e and 'dimLine' in e]
        by_pole = {}
        for e in dims:
            by_pole.setdefault((e['xLine2']['x'], e['xLine2']['y']), []).append(e)
        for group in by_pole.values():
            for i, a in enumerate(group):
                for b in group[i + 1:]:
                    wa, wb = ph.label_w(a['text']), ph.label_w(b['text'])
                    overlap_x = abs(a['textPosition']['x'] - b['textPosition']['x']) < (wa + wb) / 2
                    overlap_y = abs(a['textPosition']['y'] - b['textPosition']['y']) < ph.LABEL_H
                    self.assertFalse(overlap_x and overlap_y, (a['text'], b['text']))

    def test_rows_follow_the_cluster_rule(self):
        items = [dict(t='dot', h="16'2\"", c=[]), dict(t='dot', h="16'5\"", c=[]),
                 dict(t='dot', h="17'5\"", c=[]), dict(t='dot', h="17'8\"", c=[]), dict(t='dot', h="28'6\"", c=[])]
        ph.assign_rows(items)
        self.assertEqual([it['row'] for it in items], [54, 62, 70, 78, 142])

    def test_elev_is_a_bare_number(self):
        J = ph.Job()
        ph.build_sheet(J, 0, 0, dict(pole='X', notes=['-A'], gps=['1', '2'], elev="821'"))
        footage = [e for _, h, e in J.edits if h == ph.ELEV[0]]
        self.assertEqual(footage[0]['attributes']['FOOTAGE'], '821')

    def test_elev_lead_line_copied_with_elev(self):
        J = ph.Job()
        ph.build_sheet(J, 0, 0, dict(pole='X', notes=['-A'], gps=['1', '2'], elev='821'))
        ops = [op for _, op in J.ops if ph.ELEV[0] in op['handles']]
        self.assertEqual(ops[0]['handles'], [ph.ELEV[0], ph.ELEV_LEAD])

    def test_street_only(self):
        self.assertEqual(ph.street_only('1065 Burtonwood Ave, Thousand Oaks CA'), '1065 BURTONWOOD AVE')


class StationBuilderTests(unittest.TestCase):
    def test_fills_and_dedupes(self):
        rows = [(None, None, None)] * 43
        rows = [list(r) for r in rows]
        rows[5] = [None, "34°11'32.19\"", None]
        rows[7] = [None, "118°53'1.0\"", None]
        rows[9] = [None, "821'", None]
        rows[23] = ['POLE SET IN ______, INSP. ______', '2018,  INSP. N/A', None]
        rows[24] = ['TRUCK ACCESS VIA STREET NAME', 'Windsor Dr', None]
        rows[25] = ['TRUCK ACCESS VIA STREET NAME', 'Windsor Dr', None]
        out = sbm.sheet_from_rows('P', [tuple(r) for r in rows], [])
        self.assertEqual(out['notes'], ['-POLE SET IN 2018, INSP. N/A', '-TRUCK ACCESS VIA WINDSOR DR'])
        self.assertEqual(out['elev'], '821')


    def test_fill_ins_in_column_q(self):
        # TD2536074: every fill-in sat in column Q, whole access notes included, with "NA" and comma-split years
        rows = [[None, None, None, None] for _ in range(43)]
        rows[5][1], rows[7][1] = "34\u00b011'56.58\"", "118\u00b051'40.57\""
        rows[23] = ['-POLE SET IN ______, INSP. ______', None, None, '2014 , NA']
        rows[24] = ['-ACCESS VIA STREET NAME', None, None, 'FOOT ACCESS VIA REAR PROPERTY OF 986 WAVERLY HEIGHTS DR']
        rows[25] = ['-TRUCK ACCESS VIA STREET NAME', None, None, 'WINDSOR DR']
        rows[26] = ['C0MM ANCHOR BEING ISNTALLED AT 4\'5"', None, None, '  ']
        out = sbm.sheet_from_rows('P', [tuple(r) for r in rows], [])
        self.assertEqual(out['notes'], ['-POLE SET IN 2014, INSP. N/A',
                                        '-FOOT ACCESS VIA REAR PROPERTY OF 986 WAVERLY HEIGHTS DR',
                                        '-TRUCK ACCESS VIA WINDSOR DR', '-COMM ANCHOR BEING INSTALLED AT 4\'5"'])


class ShortArmTest(unittest.TestCase):
    def test_arm1_left_with_dot_at_the_end(self):
        J = ph.Job()
        a = ph.place_item(J, 100.0, -50.0, dict(t='arm1', k='L', h="18'"), -1)
        self.assertEqual(a, 17.5)                  # callouts on the arm side: dim attaches at the arm end
        line = [e for _, h, e in J.edits if h == ph.GALINE[0]][0]
        self.assertEqual((line['start']['x'], line['end']['x']), (82.5, 100.0))
        dot = [op for _, op in J.ops if op['handles'] == ph.SRC['dot']['h']][0]
        self.assertAlmostEqual(dot['dx'] + ph.SRC['dot']['px'], 82.5, places=3)
        self.assertEqual(ph.place_item(ph.Job(), 100.0, -50.0, dict(t='arm1', k='L', h="18'"), 1), 0)


class NewRulesTest(unittest.TestCase):
    def _sheet(self, **kw):
        J = ph.Job()
        sheet = dict(pole='1312225E', notes=['-X'], gps=['', ''], elev='')
        sheet.update(kw)
        ph.build_sheet(J, 0, 0, sheet)
        return J

    def test_tlm_load_has_no_percent(self):
        J = self._sheet(tlm=dict(ex=['37.5', '46.3', '12', '123.47%'], pr=['50', '1', '1', '113.72 %'], addr=[]))
        attrs = [e['attributes'] for k, h, e in J.edits if h == ph.TLM[0]][0]
        self.assertEqual((attrs['EX-LOAD'], attrs['PR-LOAD']), ('123.47', '113.72'))

    def test_tlm_burst_rows(self):
        addr = [['%d MAIN ST' % i, 'M%d' % i] for i in range(12)]
        J = self._sheet(tlm=dict(addr=addr, notes=['A']))
        e = [e for k, h, e in J.edits if h == ph.TLM[0]][0]
        self.assertEqual(e['dynamicProperties']['ADDRESS LIST'], 'ADDRESS LIST 10')
        rows = [op for k, op in J.ops if op['handles'] == ph.TLM_EXTRA['h']]
        self.assertEqual(len(rows), 2)
        iy = 114.314
        self.assertAlmostEqual(rows[0]['dy'], iy - ph.TLM_L10_BOTTOM - ph.TLM_EXTRA['top'], 3)
        self.assertAlmostEqual(rows[0]['dy'] - rows[1]['dy'], ph.TLM_ROW, 3)
        box = [e for k, h, e in J.edits if h == ph.TLMNOTE['box']][0]
        self.assertAlmostEqual(box['vertices'][0]['y'], iy - ph.TLM_L10_BOTTOM - 2 * ph.TLM_ROW, 3)

    def test_cutout_never_mirrored(self):
        for it in (dict(t='pri', h="32'", c=['A'], k='R', fhla=True), dict(t='fhla', h="34'", c=['A'], k='R'),
                   dict(t='de1', h="33'", c=['A'], fhla='R'), dict(t='fhla', h="34'", c=['A'])):
            J = ph.Job()
            ph.place_item(J, 100, 0, it, 1)
            ops = [op for k, op in J.ops if ph.CUTOUT_SIDE[0] in op['handles']]
            self.assertEqual(len(ops), 1)
            self.assertNotIn('mirrorX', ops[0])
            left = it.get('k') == 'R' or it.get('fhla') == 'R'
            want = {'pri': -3.3132, 'fhla': -3.3132, 'de1': -8.3132}[it['t']] if left else 3.2159
            self.assertAlmostEqual(ops[0]['dx'] + ph.CUTOUT_SIDE[1], 100 + want, 3)

    def test_missing_height_label(self):
        J = ph.Job()
        ph.build_pole(J, 0, 0, dict(L='L/N', side='R', num='1',
                                    items=[dict(t='xl', h="27'", label="_'", c=['1/0AT 120V'])]))
        self.assertEqual([e['text'] for k, h, e in J.edits if h == ph.HDIM[0]], ["_'"])

    def test_single_profile_slot(self):
        def P(prof):
            J = ph.build_job(dict(poles=[dict(frame=0, pole='1', profiles=[prof], notes=['-X'])]))
            line = [e for k, h, e in J.edits if h == ph.LINE[0]][0]   # pole line starts at (P, G)
            return line['start']['x'] - ph.COLS[0]
        base = dict(side='R', items=[dict(t='xb', h="20'", c=['COMM'])])
        self.assertAlmostEqual(P(dict(base, L='L/N')), -300)
        self.assertAlmostEqual(P(dict(base, L='L/E')), 300)
        self.assertAlmostEqual(P(dict(base, L='L/NW', slot='R')), 300)

    def test_pick_tlm_extra(self):
        top, bot = -779.9231, -791.6558
        ext = lambda y0, y1: dict(min=dict(x=1854.666, y=y0), max=dict(x=1999.2395, y=y1))
        ents = [dict(handle='A', type='TEXT', text='ADDRESS12', extents=ext(-787.9, -783.1)),
                dict(handle='M', type='TEXT', text='METER12', extents=ext(-788.2, -783.4)),
                dict(handle='B13', type='LWPOLYLINE', extents=ext(-803.3884, bot)),
                dict(handle='B12', type='LWPOLYLINE', extents=ext(bot, top)),
                dict(handle='L11', type='LINE', extents=ext(top, -768.1905)),
                dict(handle='L12', type='LINE', extents=ext(bot, top))]
        self.assertEqual(ph.pick_tlm_extra(ents), ['A', 'M', 'B12', 'L12'])

    def test_tlm_rows_to_frame_bottom(self):
        # TD2486645 68718E: 60 customers all fit; more than fit is reported
        J = self._sheet(tlm=dict(addr=[['%d A ST' % i, ''] for i in range(60)], notes=['A', 'B']))
        self.assertEqual(len([op for k, op in J.ops if op['handles'] == ph.TLM_EXTRA['h']]), 50)
        self.assertFalse(any('TLM addresses' in r for r in J.report))
        J = self._sheet(tlm=dict(addr=[['%d A ST' % i, ''] for i in range(70)]))
        self.assertTrue(any('70 TLM addresses' in r for r in J.report))

    def test_street_only_keeps_unit(self):
        self.assertEqual(ph.street_only('718 N MARKET ST APT 3 '), '718 N MARKET ST APT 3')
        self.assertEqual(ph.street_only('1065 BURTONWOOD AVE THOUSAND OAKS CA'), '1065 BURTONWOOD AVE')

    def test_fhlaf_sa_layout(self):
        # Kevin's TD2486645 68719E correction: SAs -/+24.4618 (never mirrored), CUTOUTs -19.5139 / +19.5904, one XARM
        J = ph.Job()
        ph.place_item(J, 0, 0, dict(t='fhlaf', ends='sa', pins=[0, 1, 3], slant={'0': 'L'}), 1)
        sa = [(op['dx'] + 5147.4442, op.get('mirrorX')) for k, op in J.ops if op['handles'] == ['2E382D']]
        self.assertEqual([(round(x, 4), m) for x, m in sa], [(-24.4618, None), (24.4618, None)])
        co = sorted(round(op['dx'] + 5167.1696, 4) for k, op in J.ops if op['handles'] == ['2E382F'])
        self.assertEqual(co, [-19.5139, 19.5904])
        self.assertEqual(sum(op['handles'].count(ph.SRC['arm']['h'][0]) for k, op in J.ops), 1)

    def test_xcond_starts_at_side_box(self):
        # TD2486645 659344E 21'6": box R centered, X COND from the box edge
        J = ph.Job()
        a = ph.place_item(J, 0, 0, dict(t='xr', box='R'), 1)
        op = next(op for k, op in J.ops if op['handles'] == ph.SRC['xr']['h'])
        self.assertAlmostEqual(op['dx'] + ph.SRC['xr']['px'], 5)
        self.assertEqual(a, 30)
        J = ph.Job()
        ph.place_item(J, 0, 0, dict(t='xb', box='R', boxup=True), 1)
        op = next(op for k, op in J.ops if op['handles'] == ph.SRC['xr']['h'])
        self.assertAlmostEqual(op['dx'] + ph.SRC['xr']['px'], 0)

    def test_pri_dot_under_box(self):
        # TD2486645 4352147E 32'6": dot centered under the right box, 4.0 below the row
        J = ph.Job()
        ph.place_item(J, 0, 0, dict(t='pri', k='R', dot=True), 1)
        op = next(op for k, op in J.ops if op['handles'] == ph.SRC['dot']['h'])
        self.assertAlmostEqual(op['dx'] + ph.SRC['dot']['px'], 2.5)
        self.assertAlmostEqual(op['dy'] + ph.SRC['dot']['py'], -4.0)
        # TD2486645 1495939E 32'6": one-way dead end right, dot under the right box
        J = ph.Job()
        ph.place_item(J, 0, 0, dict(t='de1', k='R', nopins=True, dot=True), 1)
        op = next(op for k, op in J.ops if op['handles'] == ph.SRC['dot']['h'])
        self.assertAlmostEqual(op['dx'] + ph.SRC['dot']['px'], 2.5)
        self.assertAlmostEqual(op['dy'] + ph.SRC['dot']['py'], -4.0)

    def test_pinx_boxup_stlt(self):
        J = ph.Job()
        ph.place_item(J, 0, 0, dict(t='arm', pinx=[9.755, 19.755, 29.755]), 1)
        xs = sorted(op['dx'] + ph.SRC['arm']['px'] + ph.ARM_SLOT_X[0] for k, op in J.ops if op['handles'] == [ph.ARM_PINS[0]])
        self.assertEqual([round(x, 3) for x in xs], [9.755, 19.755, 29.755])
        J = ph.Job()
        ph.place_item(J, 0, 0, dict(t='xb', box='R', boxup=True), 1)
        op = next(op for k, op in J.ops if op['handles'] == ph.SRC['sbox']['h'])
        self.assertAlmostEqual(op['dy'] + ph.SRC['sbox']['py'], 2.5)
        J = ph.Job()
        ph.place_item(J, 0, 0, dict(t='stlt', k='C'), 1)
        self.assertEqual(J.ops[0][1]['handles'], [ph.SL_FRONT[0]])

    def test_calc_indent_under_lettered_loads(self):
        J = ph.Job()
        ph.build_calc(J, 0, 0, dict(hdr='H', rows=[['A. X', '= 1'], ['1 x 2', '= 2'], ['TOTAL', '= 3']]))
        lefts = [op['dx'] for k, op in J.ops if op['handles'] == [ph.NOTE['line'][0]]][0::2]
        self.assertAlmostEqual(lefts[1] - lefts[0], ph.CALC_INDENT, 3)
        self.assertAlmostEqual(lefts[2], lefts[0], 3)

    def test_callout_column_follows_equipment(self):
        def col(side, items):
            J = ph.Job()
            spec = dict(L='L/N', side=side, num='1', items=items)
            ph.build_pole(J, 0, 0, spec)
            return max([ph.COL_MIN] + [it['a'] + ph.COL_GAP for it in spec['items']])
        self.assertAlmostEqual(col('R', [dict(t='arm2', h="37'", c=['A'])]), 40.75)
        self.assertAlmostEqual(col('L', [dict(t='de2', h="37'", c=['A'])]), 35.75)
        self.assertAlmostEqual(col('R', [dict(t='xb', h="20'", c=['COMM'])]), 30.75)

    def test_slanted_pin_replaces_upright(self):
        for t in ('arm4', 'arm'):
            J = ph.Job()
            it = dict(t=t, h="37'", c=['A'], slant={'0': 'L', '3': 'R'})
            if t == 'arm':
                it['pins'] = [0, 1, 3]
            ph.build_pole(J, 100, 0, dict(L='L/N', side='R', num='1', items=[it]))
            hs = [h for k, op in J.ops for h in op['handles']]
            self.assertNotIn('2E3401', hs)                  # slots 0 and 3 lose their upright pins
            self.assertNotIn('2E3403', hs)
            self.assertIn('2E3402', hs)
            row = ph.pos(37)
            for h, slot in (('2E3477', 0), ('2E3472', 3)):
                op = next(op for k, op in J.ops if op['handles'] == [h])
                _, ix, iy = ph.SLANT_PIN['L' if h == '2E3477' else 'R']
                self.assertAlmostEqual(ix + op['dx'], 100 + ph.ARM_SLOT_X[slot], 3)
                self.assertAlmostEqual(iy + op['dy'], row, 3)   # base on the arm line (TD2486645)
                self.assertNotIn('mirrorX', op)

    def test_slant_rejected_without_pins(self):
        with self.assertRaises(ValueError):
            ph.place_item(ph.Job(), 0, 0, dict(t='armc', h="37'", slant={'0': 'L'}), 1)


class AnchorIndexTest(unittest.TestCase):
    def test_guys_follow_listed_anchor_order(self):
        """Far anchor listed first: guys with an=0 must still go to the far anchor (TD2536031 bug)."""
        spec = {"job": "T", "poles": [{"frame": 0, "pole": "1296866E", "profiles": [{
            "L": "L/E", "side": "L", "gside": 1,
            "items": [{"t": "dot", "h": "31'", "c": ["X"]}, {"t": "dot", "h": "22'6\"", "c": ["COMM"]}],
            "anchors": [{"L": "26'11\"", "c": "IN"}, {"L": "23'6\"", "c": "EX: COMM ANCHOR"}],
            "guys": [{"h": "31'", "an": 0, "c": "IN: DG"}, {"h": "22'6\"", "an": 1, "c": "EX: COMM DG"}]}]}]}
        J = ph.build_job(spec)
        guys = [e for _, h, e in J.edits if h == ph.GUY[0]]
        P = ph.frame(0)[0] + 300
        far, near = P + ph.anchor_base(23) + 4 * 3, P + ph.anchor_base(23)
        self.assertAlmostEqual(guys[0]['vertices'][1]['x'], round(far, 4), places=3)
        self.assertAlmostEqual(guys[1]['vertices'][1]['x'], round(near, 4), places=3)


if __name__ == '__main__':
    unittest.main()


class TestRiser(unittest.TestCase):
    def test_riser_touches_pole_and_text_side(self):
        import math
        sheet = dict(pole='1879680E', profiles=[dict(L='L/N')], notes=['-X'],
                     riser=dict(items=[dict(c='SEC', deg=195), dict(c='PRI', deg=-70)]))
        J = ph.Job()
        ph.build_riser(J, 1326.117, -3086.0311, sheet)
        Px, Py = 1326.117 + 50.9461, -3086.0311 - 150.3311
        circles = [op for _, op in J.ops if op['handles'] in (['3925C4'], ['392550'])]
        for op, r, (h, cx, cy) in zip(circles, (3.315, 3.9), (ph.RISER_CIRCLE[3], ph.RISER_CIRCLE[5])):
            x, y = cx + op['dx'], cy + op['dy']
            self.assertAlmostEqual(math.hypot(x - Px, y - Py), 12.604 + r, places=3)
        texts = [op for _, op in J.ops if op['handles'] == ['39269A']]
        self.assertNotIn('mirrorX', texts[0])      # left side riser: right justified, no mirror
        self.assertIn('mirrorX', texts[1])         # right side: mirrored to left justified
        names = [e['text'] for _, h, e in J.edits if h in ('39256C', '39256D')]
        self.assertEqual(names, ['1879', '680E'])


class TestRiserGuards(unittest.TestCase):
    def test_four_inch_radius_and_uguard_angles(self):
        sheet = dict(pole='1879680E', profiles=[dict(L='L/N')],
                     riser=dict(items=[dict(c='4" COMM', size=4, deg=120)], guards=[dict(t='uguard', deg=-45)]))
        J = ph.Job()
        ph.build_riser(J, 0.0, 0.0, sheet)
        eds = {h: e for _, h, e in J.edits}
        self.assertEqual(eds['3925C4'], dict(radius=3.6075))
        u = eds['3926EA']
        self.assertAlmostEqual(u['startAngleDeg'], 224.9, places=3)
        self.assertAlmostEqual(u['endAngleDeg'], 45.1, places=3)
        self.assertEqual(J.report, [])


def _pole(items, **prof):
    """One-profile, one-pole spec on frame 0 (left slot: P = -843.912, G = -3575.8251)."""
    p = dict(L='L/N', side='R', items=items)
    p.update(prof)
    return dict(job='T', poles=[dict(frame=0, pole='1E', profiles=[p], crew=[], notes=['-X'], gps=['1', '2'], elev='1')])


P0, G0 = -843.912, -3575.8251


class FasterDraftingTests(unittest.TestCase):
    """TD2561109 hand pieces now placed by the generator (positions match what Kevin approved there)."""

    def ops(self, spec):
        J = ph.build_job(spec)
        return J, [op for _, op in J.ops]

    def test_soil_box_under_lead_dims_and_clear_of_pole_label(self):
        spec = _pole([dict(t='xl', h="20'", c=['COMM'])], side='L', gside=1, soil='b',
                     anchors=[dict(L="5'", c='EX: 3/4" 2EYE')], guys=[dict(h="20'", an=0, c='IN: 9/32" DG @ 20\'')])
        J, ops = self.ops(spec)
        op = next(o for o in ops if '394947' in o['handles'])
        self.assertEqual(op['handles'], ['394947', '394948'])
        left, top = ph.SOIL['left'] + op['dx'], ph.SOIL['top'] + op['dy']
        self.assertAlmostEqual(top, G0 - 20, places=3)                    # 8 below the one lead dim line
        self.assertGreaterEqual(left - (P0 - 9.86), 6 - 1e-6)             # 6 clear of the pole label
        self.assertIn(dict(text='SOIL TYPE = B'), [e for _, h, e in J.edits if h == '394948'])

    def test_no_soil_without_the_key(self):
        spec = _pole([dict(t='xl', h="20'", c=['COMM'])], side='L', gside=1,
                     anchors=[dict(L="5'", c='EX: 3/4" 2EYE')], guys=[dict(h="20'", an=0)])
        _, ops = self.ops(spec)
        self.assertFalse(any('394947' in o['handles'] for o in ops))

    def test_arm_omni_on_slots(self):
        _, ops = self.ops(_pole([dict(t='arm', h="33'", omni=[0, 2, 3], c=['HRZ OMNI SWITCH'])]))
        om = [o for o in ops if o['handles'] == ['2E344E']]
        xs = sorted(round(ph.OMNI[1] + o['dx'], 3) for o in om)
        self.assertEqual(xs, [round(P0 + ph.ARM_SLOT_X[i], 3) for i in (0, 2, 3)])
        self.assertTrue(all(abs(ph.OMNI[2] + o['dy'] - (G0 + ph.pos(33))) < 1e-6 for o in om))
        self.assertFalse(any('mirrorX' in o for o in om))
        _, ops = self.ops(_pole([dict(t='arm', h="33'", omni=[1], omni_lean='R', c=['X'])]))
        self.assertIn('mirrorX', next(o for o in ops if o['handles'] == ['2E344E']))

    def test_side_cutout_right_never_mirrored(self):
        _, ops = self.ops(_pole([dict(t='pri', h="35'6\"", k='L', cutout='R', c=['IN: FH ARM'])]))
        co = [o for o in ops if o['handles'] == ['2E3872']]
        self.assertEqual(len(co), 1)
        self.assertNotIn('mirrorX', co[0])
        self.assertAlmostEqual(ph.CUTOUT_SIDE[1] + co[0]['dx'], P0 + 3.2159, places=3)

    def test_side_cutout_left_clears_a_left_box(self):
        _, ops = self.ops(_pole([dict(t='pri', h="35'", k='L', cutout='L', c=['IN: FH ARM'])]))
        co = next(o for o in ops if o['handles'] == ['2E3872'])
        self.assertAlmostEqual(ph.CUTOUT_SIDE[1] + co['dx'], P0 - 5 - 3.3132, places=3)

    def test_centered_one_box_dead_end(self):
        _, ops = self.ops(_pole([dict(t='de2', h="36'", onebox='C', c=['IN: 3/C 336ATW'])]))
        src = ph.SRC['de1']['px']
        box = next(o for o in ops if '2E3912' in o['handles'])
        self.assertAlmostEqual(src + box['dx'], P0 - 2.5, places=3)       # right box set slid 2.5 left
        self.assertIn('2E3916', box['handles'])                           # pin on the pole
        left = next(o for o in ops if '2E3490' in o['handles'])
        self.assertAlmostEqual(src + left['dx'], P0 + 2.5, places=3)      # left ticks and X COND from the box edge
        self.assertFalse(any('2E3415' in o['handles'] for o in ops))      # no second box

    def test_share_item_needs_no_callout(self):
        ph.build_job(_pole([dict(t='dot', h="22'", c=['COMM', 'COMM SG']), dict(t='sg', h="22'", k='R', share=1)]))
